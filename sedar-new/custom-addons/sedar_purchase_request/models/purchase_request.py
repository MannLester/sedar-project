from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarPurchaseRequest(models.Model):
    _name = "sedar.purchase.request"
    _description = "SEDAR Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, required_date, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    requester_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    department_id = fields.Many2one("hr.department")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Preferred Vendor",
        domain=[("supplier_rank", ">", 0)],
        tracking=True,
    )
    source_type = fields.Selection(
        [
            ("maintenance", "Maintenance"),
            ("inventory", "Inventory"),
            ("operations", "Operations"),
            ("manual", "Manual"),
        ],
        default="manual",
        required=True,
        tracking=True,
    )
    maintenance_request_id = fields.Many2one("maintenance.request", string="Maintenance Work Order")
    service_order_id = fields.Many2one("sedar.marine.service.order", string="Service Order")
    required_date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    priority = fields.Selection(
        [("normal", "Normal"), ("urgent", "Urgent"), ("emergency", "Emergency")],
        default="normal",
        required=True,
        tracking=True,
    )
    justification = fields.Text(required=True)
    line_ids = fields.One2many("sedar.purchase.request.line", "request_id", string="Request Lines")
    purchase_order_id = fields.Many2one("purchase.order", readonly=True, copy=False)
    purchase_order_state = fields.Selection(related="purchase_order_id.state", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("po_created", "RFQ Created"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    rejected_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    rejected_at = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(copy=False)
    estimated_total = fields.Monetary(compute="_compute_estimated_total", store=True)

    @api.depends("line_ids.estimated_subtotal")
    def _compute_estimated_total(self):
        for request in self:
            request.estimated_total = sum(request.line_ids.mapped("estimated_subtotal"))

    @api.constrains("line_ids", "state")
    def _check_lines_when_progressing(self):
        for request in self:
            if request.state in {"submitted", "approved", "po_created"} and not request.line_ids:
                raise ValidationError("A submitted Purchase Request must have at least one line.")

    def _check_purchase_request_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_purchase_request.group_sedar_purchase_request_manager"):
            raise AccessError("Only a Purchase Request Manager may approve, reject, or create RFQs.")

    def action_submit(self):
        for request in self:
            if request.state not in {"draft", "rejected"}:
                raise UserError("Only draft or rejected requests can be submitted.")
            if not request.line_ids:
                raise UserError("Add at least one request line before submitting.")
            request.write({
                "state": "submitted",
                "rejection_reason": False,
                "rejected_by_id": False,
                "rejected_at": False,
            })
        return True

    def action_approve(self):
        self._check_purchase_request_manager()
        for request in self:
            if request.state != "submitted":
                raise UserError("Only submitted requests can be approved.")
            if not request.vendor_id:
                raise UserError("Set a preferred vendor before approval.")
            request.write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
        return True

    def action_reject(self):
        self._check_purchase_request_manager()
        for request in self:
            if request.state not in {"submitted", "approved"}:
                raise UserError("Only submitted or approved requests can be rejected.")
            if not request.rejection_reason:
                raise UserError("Enter a rejection reason before rejecting the request.")
            request.write({
                "state": "rejected",
                "rejected_by_id": self.env.user.id,
                "rejected_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        for request in self:
            if request.state == "po_created":
                raise UserError("A request with a created RFQ cannot be cancelled from this demo control.")
        self.write({"state": "cancelled"})
        return True

    def action_create_rfq(self):
        self._check_purchase_request_manager()
        purchase_orders = self.env["purchase.order"]
        for request in self:
            if request.state != "approved":
                raise UserError("Only approved requests can create an RFQ.")
            if request.purchase_order_id:
                raise UserError("This Purchase Request already has an RFQ.")
            if not request.vendor_id:
                raise UserError("Set a preferred vendor before creating an RFQ.")
            order_lines = []
            for line in request.line_ids:
                order_lines.append(fields.Command.create({
                    "product_id": line.product_id.id,
                    "name": line.product_id.display_name,
                    "product_qty": line.quantity,
                    "product_uom_id": line.product_uom_id.id,
                    "price_unit": line.estimated_unit_price,
                    "date_planned": request.required_date,
                }))
            purchase_order = self.env["purchase.order"].create({
                "partner_id": request.vendor_id.id,
                "company_id": request.company_id.id,
                "currency_id": request.currency_id.id,
                "origin": request.name,
                "date_order": fields.Datetime.now(),
                "date_planned": request.required_date,
                "order_line": order_lines,
            })
            request.write({
                "purchase_order_id": purchase_order.id,
                "state": "po_created",
            })
            purchase_orders |= purchase_order
        return self._action_open_purchase_order(purchase_orders)

    def _action_open_purchase_order(self, purchase_orders):
        if not purchase_orders:
            return True
        action = {
            "type": "ir.actions.act_window",
            "name": "Request for Quotation",
            "res_model": "purchase.order",
            "view_mode": "form",
        }
        if len(purchase_orders) == 1:
            action["res_id"] = purchase_orders.id
        else:
            action["view_mode"] = "list,form"
            action["domain"] = [("id", "in", purchase_orders.ids)]
        return action

    def action_open_purchase_order(self):
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError("No RFQ has been created yet.")
        return self._action_open_purchase_order(self.purchase_order_id)

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for request in requests:
            if request.name == "New":
                request.name = self.env["ir.sequence"].next_by_code("sedar.purchase.request") or "New"
        return requests


class SedarPurchaseRequestLine(models.Model):
    _name = "sedar.purchase.request.line"
    _description = "SEDAR Purchase Request Line"
    _order = "request_id, sequence, product_id"

    request_id = fields.Many2one("sedar.purchase.request", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    quantity = fields.Float(required=True, default=1.0)
    estimated_unit_price = fields.Monetary(default=0.0)
    currency_id = fields.Many2one(related="request_id.currency_id", store=True, readonly=True)
    estimated_subtotal = fields.Monetary(compute="_compute_estimated_subtotal", store=True)
    source_location_id = fields.Many2one("stock.location", domain=[("usage", "=", "internal")], ondelete="set null")
    maintenance_part_line_id = fields.Many2one("sedar.maintenance.part.line", ondelete="set null")
    inventory_requirement_id = fields.Many2one("sedar.inventory.requirement", ondelete="set null")
    need_reason = fields.Text()

    @api.depends("quantity", "estimated_unit_price")
    def _compute_estimated_subtotal(self):
        for line in self:
            line.estimated_subtotal = line.quantity * line.estimated_unit_price

    @api.onchange("maintenance_part_line_id")
    def _onchange_maintenance_part_line_id(self):
        if self.maintenance_part_line_id:
            line = self.maintenance_part_line_id
            self.product_id = line.product_id
            self.quantity = max(line.shortage_qty or line.requested_qty, 1.0)
            self.source_location_id = line.source_location_id

    @api.onchange("inventory_requirement_id")
    def _onchange_inventory_requirement_id(self):
        if self.inventory_requirement_id:
            line = self.inventory_requirement_id
            self.product_id = line.product_id
            self.quantity = max(line.shortage_qty or line.required_qty, 1.0)
            self.source_location_id = line.source_location_id

    @api.constrains("quantity", "estimated_unit_price")
    def _check_quantities(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError("Purchase Request quantity must be greater than zero.")
            if line.estimated_unit_price < 0:
                raise ValidationError("Estimated unit price cannot be negative.")

    @api.constrains("maintenance_part_line_id", "inventory_requirement_id")
    def _check_single_source_line(self):
        for line in self:
            if line.maintenance_part_line_id and line.inventory_requirement_id:
                raise ValidationError("A Purchase Request line can reference either a maintenance part line or an inventory requirement, not both.")

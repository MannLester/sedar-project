from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


OFFICER_GROUP = "sedar_marine_inventory.group_marine_inventory_manager"
REVIEW_ACTIVITY_TYPE = "sedar_purchase_request.mail_activity_type_purchase_request_review"
WORKFLOW_FIELDS = {
    "name", "state", "approved_by_id", "approved_at", "rejected_by_id",
    "rejected_at", "purchase_order_id", "purchase_order_ids",
}
FACT_FIELDS = {
    "requester_id", "department_id", "company_id", "currency_id", "vendor_id",
    "source_type", "maintenance_request_id", "service_order_id", "equipment_id",
    "required_date", "priority", "justification", "line_ids",
}


class ResCompany(models.Model):
    _inherit = "res.company"

    def write(self, vals):
        result = super().write(vals)
        if "sedar_procurement_inventory_officer_id" in vals:
            for company in self:
                requests = self.env["sedar.purchase.request"].sudo().search([
                    ("company_id", "=", company.id), ("state", "=", "submitted"),
                ])
                if company.sedar_procurement_inventory_officer_id:
                    requests._reconcile_review_activity()
                else:
                    requests._close_review_activity(_(
                        "Closed because this company has no configured Procurement and Inventory Officer."
                    ))
        return result


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sedar_procurement_inventory_officer_id = fields.Many2one(
        related="company_id.sedar_procurement_inventory_officer_id", readonly=False
    )


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    sedar_purchase_request_id = fields.Many2one(
        "sedar.purchase.request", string="Purchase Request", readonly=True, copy=False,
        index=True, ondelete="set null", check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any("sedar_purchase_request_id" in vals for vals in vals_list):
            raise AccessError(_("Purchase Request order links are set only by the controlled award workflow."))
        return super().create(vals_list)

    def write(self, vals):
        if "sedar_purchase_request_id" in vals and not self.env.su:
            raise AccessError(_("Purchase Request order links are changed only by the controlled award workflow."))
        return super().write(vals)


class SedarInventoryRequirementProcurementLock(models.Model):
    _inherit = "sedar.inventory.requirement"

    def write(self, vals):
        protected = {"order_id", "product_id", "source_location_id"}.intersection(vals)
        changed = self.filtered(
            lambda requirement: any(
                getattr(requirement, field_name).id != vals[field_name]
                for field_name in protected
            )
        )
        if changed and self.env["sedar.purchase.request.line"].sudo().search_count([
            ("inventory_requirement_id", "in", changed.ids),
        ]):
            raise ValidationError(_(
                "An Inventory Requirement linked to a Purchase Request cannot change its Service Order, product, or source location."
            ))
        return super().write(vals)


class SedarPurchaseRequest(models.Model):
    _name = "sedar.purchase.request"
    _description = "SEDAR Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, required_date, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    department_id = fields.Many2one("hr.department", check_company=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    # Hidden legacy data retained for deterministic Bid migration in the next issue.
    vendor_id = fields.Many2one(
        "res.partner", string="Legacy Vendor Reference", domain=[("supplier_rank", ">", 0)],
        tracking=True, check_company=True,
    )
    source_type = fields.Selection(
        [("maintenance", "Maintenance"), ("inventory", "Inventory"),
         ("operations", "Operations"), ("manual", "Manual")],
        default="manual", required=True, tracking=True,
    )
    maintenance_request_id = fields.Many2one(
        "maintenance.request", string="Maintenance Work Order", check_company=True
    )
    service_order_id = fields.Many2one(
        "sedar.marine.service.order", string="Service Order", check_company=True
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Equipment", ondelete="restrict", check_company=True,
        help="Affected Equipment when the physical goods are needed for a specific unit.",
    )
    required_date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    priority = fields.Selection(
        [("normal", "Normal"), ("urgent", "Urgent"), ("emergency", "Emergency")],
        default="normal", required=True, tracking=True,
    )
    justification = fields.Text(required=True)
    line_ids = fields.One2many("sedar.purchase.request.line", "request_id", string="Request Lines")
    # Legacy singular fields remain readable through the upgrade window.
    purchase_order_id = fields.Many2one(
        "purchase.order", readonly=True, copy=False, check_company=True
    )
    purchase_order_state = fields.Selection(related="purchase_order_id.state", store=True)
    purchase_order_ids = fields.One2many(
        "purchase.order", "sedar_purchase_request_id", string="Purchase Orders", readonly=True
    )
    purchase_order_count = fields.Integer(
        compute="_compute_procurement_progress", compute_sudo=True, store=True
    )
    bid_ids = fields.One2many(
        "sedar.purchase.bid", "request_id", string="Bids", readonly=True,
        groups=OFFICER_GROUP,
    )
    bid_count = fields.Integer(
        compute="_compute_procurement_progress", compute_sudo=True, store=True,
        groups=OFFICER_GROUP,
    )
    procurement_progress = fields.Selection(
        [("not_started", "Not Started"), ("awaiting_approval", "Awaiting Approval"),
         ("ready_for_bids", "Ready for Bids"), ("bidding", "Bidding"),
         ("partially_awarded", "Partially Awarded"), ("fully_awarded", "Fully Awarded"),
         ("ordering", "Ordering"),
         ("ordered", "Ordered"), ("cancelled", "Cancelled")],
        compute="_compute_procurement_progress", compute_sudo=True, store=True,
        string="Procurement Progress",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
         ("po_created", "Purchase Order Created"), ("rejected", "Rejected"),
         ("cancelled", "Cancelled")],
        default="draft", required=True, tracking=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    rejected_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    rejected_at = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(copy=False)
    is_procurement_inventory_officer = fields.Boolean(
        compute="_compute_is_procurement_inventory_officer",
        string="Is Procurement and Inventory Officer",
    )
    estimated_total = fields.Monetary(compute="_compute_estimated_total", store=True)

    @api.depends("company_id.sedar_procurement_inventory_officer_id")
    @api.depends_context("uid")
    def _compute_is_procurement_inventory_officer(self):
        for request in self:
            request.is_procurement_inventory_officer = (
                self.env.user == request.company_id.sedar_procurement_inventory_officer_id
            )

    @api.depends("line_ids.estimated_subtotal")
    def _compute_estimated_total(self):
        for request in self:
            request.estimated_total = sum(request.line_ids.mapped("estimated_subtotal"))

    @api.depends(
        "state", "bid_ids.state", "purchase_order_ids.state",
        "purchase_order_id", "purchase_order_id.state",
        "line_ids.line_state", "line_ids.current_award_id.state",
    )
    def _compute_procurement_progress(self):
        for request in self:
            privileged = request.sudo()
            bids = privileged.bid_ids
            orders = privileged.purchase_order_ids | privileged.purchase_order_id
            request.bid_count = len(bids)
            request.purchase_order_count = len(orders)
            active_lines = privileged.line_ids.filtered(lambda line: line.line_state == "active")
            awarded_lines = active_lines.filtered("current_award_id")
            if request.state == "cancelled":
                progress = "cancelled"
            elif orders and all(order.state in {"purchase", "done"} for order in orders):
                progress = "ordered"
            elif orders:
                progress = "ordering"
            elif active_lines and len(awarded_lines) == len(active_lines):
                progress = "fully_awarded"
            elif awarded_lines:
                progress = "partially_awarded"
            elif bids.filtered(lambda bid: bid.state != "withdrawn"):
                progress = "bidding"
            elif request.state in {"approved", "po_created"}:
                progress = "ready_for_bids"
            elif request.state == "submitted":
                progress = "awaiting_approval"
            else:
                progress = "not_started"
            request.procurement_progress = progress

    @api.onchange("maintenance_request_id")
    def _onchange_maintenance_request_id(self):
        if self.maintenance_request_id.equipment_id:
            self.equipment_id = self.maintenance_request_id.equipment_id

    @api.constrains("company_id", "maintenance_request_id", "service_order_id", "equipment_id", "line_ids")
    def _check_source_consistency(self):
        self._validate_source_consistency()

    @api.constrains("requester_id", "company_id")
    def _check_requester_company(self):
        for request in self:
            requester = request.requester_id
            if not requester.active or requester.share or request.company_id not in requester.company_ids:
                raise ValidationError(_(
                    "The requester must be an active internal user allowed in the Purchase Request company."
                ))

    def _validate_source_consistency(self):
        for request in self:
            request._validate_header_source_consistency()
            for line in request.line_ids:
                line._validate_parent_source_consistency(request)

    def _validate_header_source_consistency(self):
        self.ensure_one()
        for record, label in (
            (self.maintenance_request_id, _("Maintenance Work Order")),
            (self.service_order_id, _("Service Order")),
            (self.equipment_id, _("Equipment")),
        ):
            if record and record.company_id and record.company_id != self.company_id:
                raise ValidationError(_(
                    "The %(source)s must belong to the Purchase Request company.",
                    source=label,
                ))
        work_order_equipment = self.maintenance_request_id.equipment_id
        if work_order_equipment and self.equipment_id != work_order_equipment:
            raise ValidationError(_(
                "Equipment must match the Equipment on the selected Maintenance Work Order."
            ))

    @api.constrains("line_ids", "state")
    def _check_lines_when_progressing(self):
        for request in self:
            if request.state in {"submitted", "approved", "po_created"} and not request.line_ids:
                raise ValidationError(_("A submitted Purchase Request must have at least one line."))

    def _get_valid_officer(self):
        self.ensure_one()
        officer = self.company_id.sedar_procurement_inventory_officer_id
        if (not officer or not officer.active or officer.share
                or self.company_id not in officer.company_ids or not officer.has_group(OFFICER_GROUP)):
            raise UserError(_(
                "Configure an active Procurement and Inventory Officer for this company before submitting or reviewing Purchase Requests."
            ))
        return officer

    def _check_procurement_inventory_officer(self):
        for request in self:
            if self.env.user != request._get_valid_officer():
                raise AccessError(_(
                    "Only the configured Procurement and Inventory Officer may approve or reject this Purchase Request."
                ))

    def _check_requester_or_officer(self):
        for request in self:
            officer = request.company_id.sedar_procurement_inventory_officer_id
            if self.env.user not in (request.requester_id | officer):
                raise AccessError(_(
                    "Only the requester or configured Procurement and Inventory Officer may change this Purchase Request."
                ))

    def _review_activity_type(self):
        return self.env.ref(REVIEW_ACTIVITY_TYPE, raise_if_not_found=False)

    def _open_review_activities(self):
        activity_type = self._review_activity_type()
        if not activity_type or not self.ids:
            return self.env["mail.activity"]
        return self.env["mail.activity"].sudo().search([
            ("active", "=", True), ("activity_type_id", "=", activity_type.id),
            ("res_model", "=", self._name), ("res_id", "in", self.ids),
        ])

    def _reconcile_review_activity(self):
        activity_type = self._review_activity_type()
        if not activity_type:
            raise UserError(_("The Purchase Request review activity type is not configured."))
        for request in self:
            self.env.cr.execute("SELECT id FROM sedar_purchase_request WHERE id = %s FOR UPDATE", [request.id])
            officer = request._get_valid_officer()
            activities = request._open_review_activities()
            primary = activities[:1]
            deadline = request._review_deadline(officer)
            if primary:
                primary.write({"user_id": officer.id, "date_deadline": deadline})
                if activities - primary:
                    (activities - primary).action_feedback(feedback=_("Closed as a duplicate Purchase Request review activity."))
                continue
            self.env["mail.activity"].sudo().create({
                "activity_type_id": activity_type.id,
                "res_model_id": self.env["ir.model"]._get_id(self._name),
                "res_id": request.id, "user_id": officer.id,
                "summary": _("Review Purchase Request %(request)s", request=request.name),
                "note": _("Review this submitted physical-goods Purchase Request."),
                "date_deadline": deadline,
            })

    def _review_deadline(self, officer):
        self.ensure_one()
        officer_context = officer.with_context(tz=officer.tz or "UTC")
        return fields.Datetime.context_timestamp(
            officer_context, self.required_date
        ).date()

    def _close_review_activity(self, feedback):
        activities = self._open_review_activities()
        if activities:
            activities.action_feedback(feedback=feedback)

    def action_submit(self):
        self._check_requester_or_officer()
        for request in self:
            if request.state not in {"draft", "rejected"}:
                raise UserError(_("Only draft or rejected requests can be submitted."))
            request._get_valid_officer()
            if not request.line_ids:
                raise UserError(_("Add at least one request line before submitting."))
            request.line_ids._validate_physical_goods()
            request._validate_source_consistency()
            request.sudo().write({
                "state": "submitted", "approved_by_id": False, "approved_at": False,
                "rejection_reason": False, "rejected_by_id": False, "rejected_at": False,
            })
            request._reconcile_review_activity()
        return True

    def action_approve(self):
        self._check_procurement_inventory_officer()
        for request in self:
            if request.state != "submitted":
                raise UserError(_("Only submitted requests can be approved."))
            request.sudo().write({"state": "approved", "approved_by_id": self.env.user.id,
                                  "approved_at": fields.Datetime.now()})
            request._close_review_activity(_("Purchase Request approved."))
        return True

    def action_reject(self):
        self._check_procurement_inventory_officer()
        if self.filtered(lambda request: request.sudo().bid_ids):
            raise UserError(_(
                "A Purchase Request with Bid history cannot return to correction. Withdraw the applicable Bid instead."
            ))
        for request in self:
            if request.state not in {"submitted", "approved"}:
                raise UserError(_("Only submitted or approved requests can be rejected."))
            if not request.rejection_reason:
                raise UserError(_("Enter a rejection reason before rejecting the request."))
            request.message_post(body=Markup("<p>%s</p>") % _(
                "Purchase Request rejected: %(reason)s",
                reason=request.rejection_reason,
            ))
            request.sudo().write({"state": "rejected", "rejected_by_id": self.env.user.id,
                                  "rejected_at": fields.Datetime.now()})
            request._close_review_activity(_("Purchase Request rejected."))
        return True

    def action_cancel(self):
        self._check_requester_or_officer()
        for request in self:
            if request.state not in {"draft", "submitted", "rejected"}:
                raise UserError(_("Only draft, submitted, or rejected Purchase Requests can be cancelled."))
            if request.sudo().purchase_order_ids or request.sudo().purchase_order_id:
                raise UserError(_("A request linked to a Purchase Order cannot be cancelled."))
            request.sudo().write({"state": "cancelled"})
            request._close_review_activity(_("Purchase Request cancelled."))
        return True

    def action_create_rfq(self):
        raise UserError(_("Direct RFQ creation is disabled. Record Bids and Line Awards before creating Purchase Orders."))

    def _action_open_purchase_orders(self, purchase_orders):
        if not purchase_orders:
            return True
        action = {"type": "ir.actions.act_window", "name": _("Purchase Orders"),
                  "res_model": "purchase.order", "view_mode": "list,form"}
        if len(purchase_orders) == 1:
            action.update({"view_mode": "form", "res_id": purchase_orders.id})
        else:
            action["domain"] = [("id", "in", purchase_orders.ids)]
        return action

    def action_open_purchase_orders(self):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        orders = self.sudo().purchase_order_ids | self.sudo().purchase_order_id
        if not orders:
            raise UserError(_("No Purchase Orders are linked yet."))
        return self._action_open_purchase_orders(orders)

    def action_open_bids(self):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bids"),
            "res_model": "sedar.purchase.bid",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
            "context": {"default_request_id": self.id},
        }

    def action_open_purchase_order(self):
        return self.action_open_purchase_orders()

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            if not self.env.su:
                forbidden = (WORKFLOW_FIELDS - {"state"}).intersection(vals)
                if forbidden or vals.get("state") not in (None, False, "draft"):
                    raise AccessError(_(
                        "Purchase Request workflow, audit, and order-link fields are changed only by controlled actions."
                    ))
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                requester = self.env["res.users"].browse(vals.get("requester_id")) or self.env.user
                if requester != self.env.user and self.env.user != company.sedar_procurement_inventory_officer_id:
                    raise AccessError(_(
                        "Only the configured Procurement and Inventory Officer may create a Purchase Request for another requester."
                    ))
            if vals.get("maintenance_request_id") and not vals.get("equipment_id"):
                maintenance = self.env["maintenance.request"].browse(vals["maintenance_request_id"])
                if maintenance.equipment_id:
                    vals["equipment_id"] = maintenance.equipment_id.id
            prepared.append(vals)
        requests = super().create(prepared)
        for request in requests:
            if request.name == "New":
                request.sudo().name = self.env["ir.sequence"].next_by_code("sedar.purchase.request") or "New"
        return requests

    def write(self, vals):
        self._check_company_integrity(vals)
        self._check_workflow_write_access(vals)
        self._check_fact_write_access(vals)
        self._check_ownership_write_access(vals)
        self._check_rejection_reason_write_access(vals)
        return super().write(self._prepare_source_write_values(vals))

    def _check_company_integrity(self, vals):
        if "company_id" not in vals:
            return
        changed = self.filtered(lambda request: request.company_id.id != vals["company_id"])
        locked = changed.filtered(
            lambda request: request.line_ids
            or request.sudo().bid_ids
            or request.sudo().purchase_order_ids
            or request.purchase_order_id
        )
        if locked:
            raise ValidationError(_(
                "A Purchase Request company cannot change after request lines or procurement records exist."
            ))

    def _check_workflow_write_access(self, vals):
        if WORKFLOW_FIELDS.intersection(vals) and not self.env.su:
            raise AccessError(_("Purchase Request workflow, audit, and order-link fields are changed only by controlled actions."))

    def _check_fact_write_access(self, vals):
        if {"company_id", "currency_id", "line_ids"}.intersection(vals) and not self.env.su:
            if self.filtered(lambda request: request.sudo().bid_ids):
                raise AccessError(_(
                    "Purchase Request company, currency, and line baseline are locked after Bid capture begins."
                ))
        if FACT_FIELDS.intersection(vals) and not self.env.su and self.filtered(
                lambda request: request.state not in {"draft", "rejected"}):
            raise AccessError(_("Submitted Purchase Request facts are locked. Reject the request before correcting it."))
        if FACT_FIELDS.intersection(vals) and not self.env.su:
            self._check_requester_or_officer()

    def _check_ownership_write_access(self, vals):
        if {"requester_id", "company_id"}.intersection(vals) and not self.env.su:
            for request in self:
                if self.env.user != request.company_id.sedar_procurement_inventory_officer_id:
                    raise AccessError(_(
                        "Only the configured Procurement and Inventory Officer may change request ownership or company."
                    ))
            if "company_id" in vals:
                target_company = self.env["res.company"].browse(vals["company_id"])
                if self.env.user != target_company.sedar_procurement_inventory_officer_id:
                    raise AccessError(_(
                        "The same Procurement and Inventory Officer must be configured for the target company."
                    ))

    def _check_rejection_reason_write_access(self, vals):
        if "rejection_reason" in vals and not self.env.su:
            unauthorized = self.filtered(
                lambda request: self.env.user
                != request.company_id.sedar_procurement_inventory_officer_id
            )
            if unauthorized:
                raise AccessError(_("Only the configured Procurement and Inventory Officer may enter a review rejection reason."))

    def _prepare_source_write_values(self, vals):
        vals = dict(vals)
        if vals.get("maintenance_request_id") and "equipment_id" not in vals:
            maintenance = self.env["maintenance.request"].browse(vals["maintenance_request_id"])
            if maintenance.equipment_id:
                vals["equipment_id"] = maintenance.equipment_id.id
        return vals


class SedarPurchaseRequestLine(models.Model):
    _name = "sedar.purchase.request.line"
    _description = "SEDAR Purchase Request Line"
    _rec_name = "product_id"
    _order = "request_id, sequence, product_id"
    _check_company_auto = True

    request_id = fields.Many2one("sedar.purchase.request", required=True, ondelete="cascade", index=True, check_company=True)
    company_id = fields.Many2one(related="request_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict", check_company=True)
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    quantity = fields.Float(required=True, default=1.0)
    estimated_unit_price = fields.Monetary(default=0.0)
    currency_id = fields.Many2one(related="request_id.currency_id", store=True, readonly=True)
    estimated_subtotal = fields.Monetary(compute="_compute_estimated_subtotal", store=True)
    source_location_id = fields.Many2one(
        "stock.location", domain=[("usage", "=", "internal")], ondelete="set null", check_company=True
    )
    maintenance_part_line_id = fields.Many2one("sedar.maintenance.part.line", ondelete="set null")
    inventory_requirement_id = fields.Many2one(
        "sedar.inventory.requirement", ondelete="set null", check_company=True
    )
    need_reason = fields.Text()
    bid_line_ids = fields.One2many(
        "sedar.purchase.bid.line", "request_line_id", string="Bid Lines",
        readonly=True, groups=OFFICER_GROUP,
    )

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
                raise ValidationError(_("Purchase Request quantity must be greater than zero."))
            if line.estimated_unit_price < 0:
                raise ValidationError(_("Estimated unit price cannot be negative."))

    @api.constrains("product_id")
    def _check_physical_goods(self):
        self._validate_physical_goods()

    def _validate_physical_goods(self):
        if self.filtered(lambda line: line.product_id.type != "consu"):
            raise ValidationError(_("Purchase Requests accept physical goods only; service products are not allowed."))

    def _validate_parent_source_consistency(self, request):
        self.ensure_one()
        self._validate_line_company(request.company_id)
        self._validate_maintenance_source(request)
        self._validate_inventory_source(request)

    def _validate_line_company(self, company):
        if self.product_id.company_id and self.product_id.company_id != company:
            raise ValidationError(_("Every requested product must belong to the Purchase Request company."))
        if self.source_location_id.company_id and self.source_location_id.company_id != company:
            raise ValidationError(_("Every source location must belong to the Purchase Request company."))

    def _validate_maintenance_source(self, request):
        source = self.maintenance_part_line_id
        if not source:
            return
        if source.maintenance_request_id.company_id != request.company_id:
            raise ValidationError(_("A maintenance part source must belong to the Purchase Request company."))
        if request.maintenance_request_id and source.maintenance_request_id != request.maintenance_request_id:
            raise ValidationError(_("A maintenance part line must belong to the selected Maintenance Work Order."))
        if self.product_id != source.product_id or self.source_location_id != source.source_location_id:
            raise ValidationError(_("A Purchase Request line must match its maintenance part source."))

    def _validate_inventory_source(self, request):
        source = self.inventory_requirement_id
        if not source:
            return
        if source.company_id != request.company_id:
            raise ValidationError(_(
                "An inventory requirement source must belong to the Purchase Request company."
            ))
        if request.service_order_id and source.order_id != request.service_order_id:
            raise ValidationError(_("An inventory requirement must belong to the selected Service Order."))
        if self.product_id != source.product_id or self.source_location_id != source.source_location_id:
            raise ValidationError(_("A Purchase Request line must match its inventory requirement source."))

    @api.constrains("maintenance_part_line_id", "inventory_requirement_id")
    def _check_single_source_line(self):
        for line in self:
            if line.maintenance_part_line_id and line.inventory_requirement_id:
                raise ValidationError(_(
                    "A Purchase Request line can reference either a maintenance part line or an inventory requirement, not both."
                ))

    @api.constrains(
        "request_id", "product_id", "source_location_id",
        "maintenance_part_line_id", "inventory_requirement_id",
    )
    def _check_request_source_consistency(self):
        self.mapped("request_id")._validate_source_consistency()

    @api.model_create_multi
    def create(self, vals_list):
        request_ids = {vals.get("request_id") for vals in vals_list if vals.get("request_id")}
        requests = self.env["sedar.purchase.request"].browse(request_ids)
        locked = requests.filtered(
            lambda request: request.state not in {"draft", "rejected"}
            or request.sudo().bid_ids
        )
        if locked and not self.env.su:
            raise AccessError(_("Purchase Request lines are locked after submission or Bid capture."))
        if not self.env.su:
            requests._check_requester_or_officer()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            requests = self.mapped("request_id")
            if vals.get("request_id"):
                requests |= self.env["sedar.purchase.request"].browse(vals["request_id"])
            if requests.filtered(
                    lambda request: request.state not in {"draft", "rejected"}
                    or request.sudo().bid_ids):
                raise AccessError(_("Purchase Request lines are locked after submission or Bid capture."))
            requests._check_requester_or_officer()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            requests = self.mapped("request_id")
            if requests.filtered(
                    lambda request: request.state not in {"draft", "rejected"}
                    or request.sudo().bid_ids):
                raise AccessError(_("Purchase Request lines are locked after submission or Bid capture."))
            requests._check_requester_or_officer()
        return super().unlink()

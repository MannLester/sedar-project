from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SedarReplenishmentDemand(models.Model):
    _inherit = "sedar.replenishment.demand"

    purchase_request_line_ids = fields.One2many(
        "sedar.purchase.request.line", "replenishment_demand_id", readonly=True,
    )
    purchase_request_count = fields.Integer(
        compute="_compute_procurement_summary"
    )
    incoming_purchase_qty = fields.Float(
        compute="_compute_procurement_summary"
    )

    @api.depends(
        "purchase_request_line_ids.request_id.state",
        "purchase_request_line_ids.current_award_id.purchase_order_id.state",
    )
    def _compute_procurement_summary(self):
        PurchaseOrderLine = self.env["purchase.order.line"]
        for demand in self:
            request_lines = demand.purchase_request_line_ids
            demand.purchase_request_count = len(request_lines.mapped("request_id"))
            order_lines = PurchaseOrderLine.search([
                ("sedar_purchase_request_line_id", "in", request_lines.ids),
                ("order_id.state", "in", ["purchase", "done"]),
            ]) if request_lines else PurchaseOrderLine
            demand.incoming_purchase_qty = sum(
                max(line.product_qty - line.qty_received, 0.0)
                for line in order_lines
            ) if request_lines else 0.0

    def action_create_purchase_request(self):
        self.ensure_one()
        if self.state != "open" or self.remaining_qty <= 0:
            raise UserError(_("Only an open shortage can create a Purchase Request."))
        existing = self.purchase_request_line_ids.filtered(
            lambda line: line.request_id.state not in {"cancelled"}
        )[:1]
        if existing:
            return existing.request_id._action_open_self()
        officer = self.company_id.sedar_procurement_inventory_officer_id
        requester = self.env.user
        if requester.share or self.company_id not in requester.company_ids:
            requester = officer
        if not requester:
            raise UserError(_("Configure a Procurement and Inventory Officer first."))
        request = self.env["sedar.purchase.request"].create({
            "company_id": self.company_id.id,
            "requester_id": requester.id,
            "source_type": "inventory",
            "service_order_id": self.order_id.id,
            "required_date": fields.Datetime.to_datetime(self.required_date),
            "priority": "urgent",
            "justification": _(
                "Replenish %(product)s for %(tug)s shortage %(demand)s.",
                product=self.product_id.display_name,
                tug=self.tugboat_id.display_name,
                demand=self.name,
            ),
        })
        self.env["sedar.purchase.request.line"].with_context(
            sedar_demand_line_create=True
        ).create({
            "request_id": request.id,
            "product_id": self.product_id.id,
            "quantity": self.remaining_qty,
            "replenishment_demand_qty": self.remaining_qty,
            "source_location_id": self.company_id.sedar_default_storage_location_id.id,
            "inventory_requirement_id": self.inventory_requirement_id.id,
            "replenishment_demand_id": self.id,
            "need_reason": self.name,
        })
        return request._action_open_self()


class SedarPurchaseRequest(models.Model):
    _inherit = "sedar.purchase.request"

    def _action_open_self(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Request"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }


class SedarPurchaseRequestLine(models.Model):
    _inherit = "sedar.purchase.request.line"

    replenishment_demand_id = fields.Many2one(
        "sedar.replenishment.demand", ondelete="restrict", check_company=True,
        index=True,
    )
    affected_tugboat_id = fields.Many2one(
        related="replenishment_demand_id.tugboat_id", store=True, readonly=True,
    )
    replenishment_demand_qty = fields.Float(
        string="Original Shortage Quantity", readonly=True, copy=False,
    )

    @api.constrains(
        "replenishment_demand_id", "replenishment_demand_qty", "product_id", "quantity",
        "source_location_id", "inventory_requirement_id",
    )
    def _check_replenishment_demand(self):
        for line in self.filtered("replenishment_demand_id"):
            demand = line.replenishment_demand_id
            if line.company_id != demand.company_id:
                raise ValidationError(_("The demand and Purchase Request company must match."))
            if line.product_id != demand.product_id:
                raise ValidationError(_("The demand-linked product cannot change."))
            if line.product_uom_id != demand.product_uom_id:
                raise ValidationError(_("The demand-linked unit cannot change."))
            if float_compare(
                line.quantity,
                line.replenishment_demand_qty,
                precision_rounding=line.product_uom_id.rounding,
            ):
                raise ValidationError(_(
                    "A demand-linked line must equal the shortage quantity captured when it was created. Add extra stock as a separate unlinked line."
                ))
            if line.source_location_id != demand.company_id.sedar_default_storage_location_id:
                raise ValidationError(_("Demand-linked purchasing must receive into the default Storage location."))
            if (
                line.inventory_requirement_id
                and line.inventory_requirement_id != demand.inventory_requirement_id
            ):
                raise ValidationError(_("The linked Inventory Requirement must match the demand."))

    def write(self, vals):
        protected = {
            "request_id", "product_id", "quantity", "source_location_id",
            "inventory_requirement_id", "replenishment_demand_id",
            "replenishment_demand_qty",
        }
        if protected.intersection(vals) and self.filtered("replenishment_demand_id"):
            raise UserError(_(
                "Demand-linked request facts are fixed. Add a separate line for additional stock."
            ))
        return super().write(vals)

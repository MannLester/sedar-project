from odoo import api, fields, models
from odoo.exceptions import UserError


class SedarMarketingTag(models.Model):
    _name = "sedar.marketing.tag"
    _description = "SEDAR Marketing Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer()

    _name_unique = models.Constraint("UNIQUE(name)", "Marketing tag names must be unique.")


class SedarMarineServiceOrder(models.Model):
    _inherit = "sedar.marine.service.order"

    priority = fields.Selection(selection_add=[("high", "High")], ondelete={"high": "set default"})
    marketing_status = fields.Selection([
        ("draft", "Draft"), ("under_review", "Under Review"),
        ("awaiting_operations", "Awaiting Operations"),
        ("quotation_prepared", "Quotation Prepared"),
        ("awaiting_customer", "Awaiting Customer Approval"),
        ("approved", "Approved"), ("scheduled", "Scheduled"),
        ("completed", "Completed"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, tracking=True, index=True, copy=False)
    marketing_representative_id = fields.Many2one(
        "res.users", string="Assigned Marketing Representative", tracking=True,
        default=lambda self: self.env.user,
    )
    requested_operations_reviewer_id = fields.Many2one(
        "res.users", string="Requested Operations Reviewer", tracking=True
    )
    marketing_tag_ids = fields.Many2many(
        "sedar.marketing.tag", "sedar_service_order_marketing_tag_rel",
        "order_id", "tag_id", string="Marketing Tags"
    )
    marketing_internal_notes = fields.Text(string="Marketing Internal Notes", tracking=True)
    marketing_follow_up_date = fields.Date(string="Marketing Follow-up Date", tracking=True)
    marketing_quotation_ids = fields.One2many(
        "sedar.marketing.quotation", "service_order_id", string="Marketing Quotations"
    )
    marketing_contract_ids = fields.One2many(
        "sedar.marketing.contract", "service_order_id", string="Marketing Contracts"
    )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if order.client_id.sedar_is_customer_account:
                self.env["sedar.marketing.activity"].log(
                    order.client_id, "service_requests", "created",
                    f"Service Request {order.name} created.", order,
                )
                self.env["sedar.marketing.transaction"].sync_service_order(order)
        return orders

    def write(self, vals):
        watched = {
            "marketing_status", "marketing_representative_id", "marketing_follow_up_date",
            "priority", "requested_start", "service_type_id", "assisted_vessel_name", "state",
        }
        before = {order.id: {name: order[name] for name in watched.intersection(vals)} for order in self}
        result = super().write(vals)
        if self.env.context.get("sedar_skip_marketing_log"):
            return result
        for order in self:
            if not order.client_id.sedar_is_customer_account:
                continue
            sync_status = False
            if order.state in {"completed", "billing_ready", "closed"} and order.marketing_status != "completed":
                sync_status = "completed"
            elif order.state == "cancelled" and order.marketing_status != "cancelled":
                sync_status = "cancelled"
            elif order.state in {"planning", "blocked", "ready", "dispatched", "in_progress"} and order.marketing_status == "approved":
                sync_status = "scheduled"
            if sync_status:
                order.with_context(sedar_skip_marketing_log=True).write({"marketing_status": sync_status})
            changes = [
                (name, before[order.id].get(name), order[name])
                for name in watched.intersection(vals)
                if before[order.id].get(name) != order[name]
            ]
            if changes:
                action = "status_changed" if "marketing_status" in vals or "state" in vals else "updated"
                self.env["sedar.marketing.activity"].log(
                    order.client_id, "service_requests", action,
                    f"Service Request {order.name} updated.", order, changes,
                )
            self.env["sedar.marketing.transaction"].sync_service_order(order)
        return result

    def _set_marketing_status(self, expected, target):
        for order in self:
            if order.marketing_status not in expected:
                raise UserError(
                    f"Service Request {order.name} cannot move from {order.marketing_status} to {target}."
                )
            order.write({"marketing_status": target})
        return True

    def action_marketing_submit_review(self):
        self.filtered(lambda item: item.state == "draft").action_submit()
        return self._set_marketing_status({"draft"}, "under_review")

    def action_marketing_send_operations(self):
        return self._set_marketing_status({"under_review"}, "awaiting_operations")

    def action_marketing_prepare_quotation(self):
        return self._set_marketing_status({"under_review", "awaiting_operations"}, "quotation_prepared")

    def action_marketing_send_customer(self):
        self.filtered(lambda item: item.state in {"submitted", "review", "pricing"}).action_quote()
        return self._set_marketing_status({"quotation_prepared"}, "awaiting_customer")

    def action_marketing_approve(self):
        for order in self:
            if order.marketing_status != "awaiting_customer":
                raise UserError("Only a Service Request awaiting customer approval can be approved.")
            if order.state == "quoted":
                order.action_confirm()
            order.write({"marketing_status": "approved"})
        return True

    def action_marketing_cancel(self):
        allowed = {
            "draft", "under_review", "awaiting_operations", "quotation_prepared",
            "awaiting_customer", "approved", "scheduled",
        }
        if any(order.marketing_status not in allowed for order in self):
            raise UserError("Only an open Service Request can be cancelled by Marketing.")
        self.with_context(sedar_skip_marketing_log=True).write({"marketing_status": "cancelled"})
        self.action_cancel()
        return True

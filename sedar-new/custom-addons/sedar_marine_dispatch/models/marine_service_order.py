from odoo import api, fields, models
from odoo.exceptions import UserError


class SedarMarineServiceOrder(models.Model):
    _inherit = "sedar.marine.service.order"

    operation_ids = fields.One2many("sedar.marine.operation", "order_id", string="Marine Operations")
    operation_count = fields.Integer(compute="_compute_operation_summary", store=True)
    operation_state = fields.Selection(
        [
            ("draft", "Draft"), ("dispatched", "Dispatched"),
            ("in_progress", "In Progress"), ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ], compute="_compute_operation_summary", store=True, string="Execution Status",
    )

    @api.depends("operation_ids.state")
    def _compute_operation_summary(self):
        for order in self:
            order.operation_count = len(order.operation_ids)
            order.operation_state = order.operation_ids[:1].state if order.operation_ids else False

    def action_mark_ready(self):
        for order in self:
            if order.state not in {"confirmed", "planning", "blocked"}:
                raise UserError("Only confirmed or planned orders can be marked ready.")
            if order.readiness_status != "ready":
                raise UserError("This order is not ready: %s" % order.readiness_reason)
            order.write({"state": "ready"})
        return True

    def action_create_operation(self):
        self.ensure_one()
        if self.state != "ready":
            raise UserError("Mark the service order Ready before creating an operation.")
        operation = self.operation_ids[:1]
        if not operation:
            operation = self.env["sedar.marine.operation"].create({"order_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": "Marine Operation",
            "res_model": "sedar.marine.operation",
            "res_id": operation.id,
            "view_mode": "form",
        }

    def action_open_operation(self):
        self.ensure_one()
        operation = self.operation_ids[:1]
        if not operation:
            return self.action_create_operation()
        return {
            "type": "ir.actions.act_window",
            "name": "Marine Operation",
            "res_model": "sedar.marine.operation",
            "res_id": operation.id,
            "view_mode": "form",
        }

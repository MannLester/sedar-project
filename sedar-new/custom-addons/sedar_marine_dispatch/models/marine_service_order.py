from odoo import api, fields, models
from odoo.exceptions import UserError


class SedarMarineServiceOrder(models.Model):
    _inherit = "sedar.marine.service.order"

    operation_ids = fields.One2many("sedar.marine.operation", "order_id", string="Marine Operations")
    operation_count = fields.Integer(compute="_compute_operation_summary", store=True)
    operation_state = fields.Selection(
        [
            ("awaiting_start", "Awaiting Start"),
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
        raise UserError("Readiness is automatic when tug, crew, and inventory checks pass.")

    def _sync_automated_readiness(self):
        for order in self:
            if order.state not in {"planning", "blocked", "ready"}:
                continue
            if order.readiness_status == "ready":
                assignments = order.tug_assignment_ids.filtered(lambda item: item.state != "cancelled")
                assignments.with_context(sedar_automated_dispatch=True).write({"state": "confirmed"})
                assignments.mapped("requirement_ids.crew_assignment_ids").filtered(
                    lambda item: item.state == "planned"
                ).with_context(sedar_automated_dispatch=True).write({"state": "confirmed"})
                if order.state != "ready":
                    order.with_context(sedar_readiness_sync=True).write({"state": "ready"})
                operation = order.operation_ids[:1]
                if not operation:
                    operation = self.env["sedar.marine.operation"].create({"order_id": order.id})
                operation._refresh_dispatch_snapshot()
                operation.tug_operation_ids.mapped("tugboat_id").filtered(
                    lambda tug: tug.availability_status == "available"
                ).write({"availability_status": "assigned"})
                operation.tug_operation_ids.mapped("crew_manifest_ids.crew_profile_id").filtered(
                    lambda profile: profile.availability_status == "available"
                ).write({"availability_status": "assigned"})
            elif order.state == "ready":
                order.with_context(sedar_readiness_sync=True).write({"state": "blocked"})
        return True

    def action_plan(self):
        result = super().action_plan()
        self._sync_automated_readiness()
        return result

    def action_confirm_inventory_ready(self):
        result = super().action_confirm_inventory_ready()
        self._sync_automated_readiness()
        return result

    def action_dispatch(self):
        raise UserError("Dispatch is automatic when tug, crew, and inventory readiness are complete.")

    def action_start_service(self):
        raise UserError("The assigned Tug Master's actual start commences the Marine Operation.")

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("sedar_readiness_sync") and not self.env.context.get("sedar_operation_sync"):
            readiness_inputs = {
                "service_type_id", "number_of_tugs", "tug_class_id", "required_bollard_pull",
                "scope_of_work", "special_instructions", "port_id", "origin_berth_id",
                "destination_berth_id", "requested_start", "estimated_duration_hours",
                "hazardous_cargo", "cargo_description", "permit_required", "safety_requirements",
                "inventory_ready",
            }
            if readiness_inputs.intersection(vals):
                self._sync_automated_readiness()
        return result

    def action_create_operation(self):
        self.ensure_one()
        if self.state != "ready":
            raise UserError("The Service Order must pass automated readiness before an operation exists.")
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

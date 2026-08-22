from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarMarineServiceOrder(models.Model):
    _inherit = "sedar.marine.service.order"

    inventory_requirement_ids = fields.One2many(
        "sedar.inventory.requirement",
        "order_id",
        string="Inventory Requirements",
    )
    inventory_requirement_count = fields.Integer(compute="_compute_inventory_summary", store=True)
    inventory_auto_ready = fields.Boolean(compute="_compute_inventory_summary", store=True)
    inventory_shortage_summary = fields.Char(compute="_compute_inventory_summary", store=True)

    @api.depends(
        "inventory_requirement_ids.readiness_state",
        "inventory_requirement_ids.shortage_qty",
        "inventory_requirement_ids.product_id",
    )
    def _compute_inventory_summary(self):
        for order in self:
            requirements = order.inventory_requirement_ids
            order.inventory_requirement_count = len(requirements)
            shortages = requirements.filtered(lambda line: line.readiness_state == "shortage")
            order.inventory_auto_ready = bool(requirements) and not shortages
            order.inventory_shortage_summary = ", ".join(
                "%s: %.2f short" % (line.product_id.display_name, line.shortage_qty)
                for line in shortages[:3]
            )

    def _sync_inventory_readiness(self):
        for order in self:
            if order.inventory_requirement_ids:
                order.with_context(sedar_readiness_sync=True).write({
                    "inventory_ready": order.inventory_auto_ready,
                    "inventory_ready_by_id": False,
                    "inventory_ready_at": False,
                })
        return True

    @api.depends(
        "state", "number_of_tugs", "tug_assignment_ids.state",
        "tug_assignment_ids.tugboat_id.availability_status",
        "tug_assignment_ids.requirement_ids.required_count",
        "tug_assignment_ids.requirement_ids.crew_assignment_ids.state",
        "tug_assignment_ids.requirement_ids.gap_count",
        "tug_assignment_ids.requirement_ids.compliance_issue_count",
        "inventory_ready",
        "inventory_auto_ready",
        "inventory_requirement_ids.readiness_state",
    )
    def _compute_readiness(self):
        for order in self:
            assignments = order.tug_assignment_ids.filtered(
                lambda assignment: assignment.state != "cancelled"
            )
            order.tug_assignment_count = len(assignments)
            order.readiness_status, order.readiness_reason = order._readiness_result(assignments)

    def _readiness_result(self, assignments):
        self.ensure_one()
        if not assignments:
            early_states = {"draft", "submitted", "review", "needs_info", "pricing", "quoted"}
            if self.state in early_states:
                return "not_planned", "Order has not reached operations planning."
            return "waiting_tug", "No tugboat has been assigned."
        if len(assignments) < self.number_of_tugs:
            return "waiting_tug", "%s of %s requested tugboats are assigned." % (
                len(assignments), self.number_of_tugs,
            )
        unavailable = assignments.filtered(lambda assignment: not assignment.tug_available)
        if unavailable:
            return "blocked_tug", "Unavailable tugboat: %s" % ", ".join(
                unavailable.mapped("tugboat_id.name")
            )
        requirements = assignments.mapped("requirement_ids")
        if not requirements:
            return "waiting_crew", "Manning requirements have not been generated."
        if requirements.filtered(lambda requirement: requirement.compliance_issue_count):
            return "blocked_crew", "Crew certificate, medical, leave, rank, or schedule issue."
        shortages = requirements.filtered(lambda requirement: requirement.gap_count)
        if shortages:
            return "blocked_crew", "Unfilled manning requirement: %s" % ", ".join(
                shortages.mapped("rank_id.name")
            )
        if self.inventory_requirement_ids and not self.inventory_auto_ready:
            return "waiting_inventory", self.inventory_shortage_summary or "Required inventory is short."
        if not self.inventory_requirement_ids and not self.inventory_ready:
            return "waiting_inventory", "Inventory requirements have not been generated."
        return "ready", "Tugboat, minimum compliant crew, and inventory are ready."

    def _find_inventory_template(self):
        self.ensure_one()
        domain = [
            ("service_type_id", "=", self.service_type_id.id),
            ("active", "=", True),
            "|", ("tug_class_id", "=", self.tug_class_id.id),
            ("tug_class_id", "=", False),
        ]
        return self.env["sedar.inventory.template"].search(domain, order="tug_class_id desc, id", limit=1)

    def action_generate_inventory_requirements(self):
        for order in self:
            template = order._find_inventory_template()
            if not template:
                continue
            existing_auto = order.inventory_requirement_ids.filtered("auto_generated")
            existing_auto.unlink()
            for line in template.line_ids:
                multiplier = order.number_of_tugs if line.per_tug else 1
                self.env["sedar.inventory.requirement"].create({
                    "order_id": order.id,
                    "source_location_id": template.source_location_id.id,
                    "product_id": line.product_id.id,
                    "required_qty": line.required_qty * multiplier,
                    "auto_generated": True,
                })
            order._sync_inventory_readiness()
        return True

    def action_confirm_inventory_ready(self):
        if self.filtered("inventory_requirement_ids"):
            raise UserError("Inventory readiness is stock-derived. Resolve the listed inventory shortages instead.")
        return super().action_confirm_inventory_ready()

    def action_plan(self):
        result = super().action_plan()
        self.action_generate_inventory_requirements()
        self._sync_inventory_readiness()
        self._sync_automated_readiness()
        return result

    def write(self, vals):
        result = super().write(vals)
        inventory_inputs = {
            "service_type_id", "number_of_tugs", "tug_class_id",
            "requested_start", "estimated_duration_hours",
        }
        if inventory_inputs.intersection(vals) and not self.env.context.get("sedar_inventory_sync"):
            eligible = self.filtered(lambda order: order.state in {"planning", "blocked", "ready"})
            eligible.with_context(sedar_inventory_sync=True).action_generate_inventory_requirements()
            eligible._sync_automated_readiness()
        return result


class SedarInventoryRequirement(models.Model):
    _name = "sedar.inventory.requirement"
    _description = "Service Order Inventory Requirement"
    _inherit = ["sedar.inventory.mixin"]
    _order = "order_id, product_id"

    order_id = fields.Many2one("sedar.marine.service.order", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    source_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
    )
    required_qty = fields.Float(required=True, default=1.0)
    available_qty = fields.Float(compute="_compute_stock_status", store=True)
    shortage_qty = fields.Float(compute="_compute_stock_status", store=True)
    readiness_state = fields.Selection(
        [("ready", "Ready"), ("shortage", "Shortage")],
        compute="_compute_stock_status",
        store=True,
    )
    auto_generated = fields.Boolean(default=False)
    note = fields.Text()

    @api.depends("product_id", "source_location_id", "required_qty")
    def _compute_stock_status(self):
        for line in self:
            available = line._sedar_available_qty(line.product_id, line.source_location_id)
            line.available_qty = available
            line.shortage_qty = max(line.required_qty - available, 0.0)
            line.readiness_state = "ready" if line.shortage_qty <= 0 else "shortage"

    @api.constrains("required_qty")
    def _check_required_qty(self):
        for line in self:
            if line.required_qty <= 0:
                raise ValidationError("Required inventory quantity must be greater than zero.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped("order_id")._sync_inventory_readiness()
        lines.mapped("order_id")._sync_automated_readiness()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if {"product_id", "source_location_id", "required_qty"}.intersection(vals):
            self.mapped("order_id")._sync_inventory_readiness()
            self.mapped("order_id")._sync_automated_readiness()
        return result

    def unlink(self):
        orders = self.mapped("order_id")
        result = super().unlink()
        orders._sync_inventory_readiness()
        orders._sync_automated_readiness()
        return result

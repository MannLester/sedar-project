from odoo import api, fields, models
from odoo.exceptions import UserError


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
        "inventory_requirement_ids.tug_assignment_id",
    )
    def _compute_inventory_summary(self):
        for order in self:
            requirements = order.inventory_requirement_ids
            order.inventory_requirement_count = len(requirements)
            shortages = requirements.filtered(lambda line: line.readiness_state != "ready")
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
        "tug_class_id", "required_bollard_pull",
        "tug_assignment_ids.planned_start", "tug_assignment_ids.planned_end",
        "tug_assignment_ids.tugboat_id.active",
        "tug_assignment_ids.tugboat_id.availability_status",
        "tug_assignment_ids.tugboat_id.tug_class_id",
        "tug_assignment_ids.tugboat_id.bollard_pull",
        "tug_assignment_ids.tugboat_id.drydock_plan_ids.state",
        "tug_assignment_ids.tugboat_id.drydock_plan_ids.planned_start",
        "tug_assignment_ids.tugboat_id.drydock_plan_ids.planned_end",
        "tug_assignment_ids.tugboat_id.drydock_plan_ids.availability_impact",
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

    def _readiness_result(self, assignments):  # noqa: C901, PLR0911
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
        integrated_blockers = assignments.filtered(
            lambda assignment: "blocked" in {
                assignment.capability_status,
                assignment.schedule_status,
                assignment.technical_status,
            }
        )
        if integrated_blockers:
            return "blocked_tug", "; ".join(
                integrated_blockers.mapped("integrated_readiness_summary")
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
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            "|", ("tug_class_id", "=", self.tug_class_id.id),
            ("tug_class_id", "=", False),
        ]
        return self.env["sedar.inventory.template"].search(domain, order="tug_class_id desc, id", limit=1)

    def action_generate_inventory_requirements(self):
        Requirement = self.env["sedar.inventory.requirement"].with_context(
            sedar_inventory_generation=True
        )
        for order in self:
            template = order._find_inventory_template()
            if not template:
                continue
            existing_auto = order.inventory_requirement_ids.filtered("auto_generated")
            retained = self.env["sedar.inventory.requirement"]
            assignments = order.tug_assignment_ids.filtered(lambda item: item.state != "cancelled")
            for line in template.line_ids:
                targets = assignments if line.per_tug else [False]
                for assignment in targets:
                    matching = existing_auto.filtered(
                        lambda requirement: (
                            requirement.tug_assignment_id.id == (assignment.id if assignment else False)
                            and requirement.product_id == line.product_id
                        )
                    )[:1]
                    values = {
                        "order_id": order.id,
                        "tug_assignment_id": assignment.id if assignment else False,
                        "source_location_id": template.source_location_id.id,
                        "product_id": line.product_id.id,
                        "expected_consumption_qty": line.required_qty,
                        "auto_generated": True,
                    }
                    if matching:
                        matching.with_context(sedar_inventory_generation=True).write(values)
                        retained |= matching
                    else:
                        retained |= Requirement.create(values)
            (existing_auto - retained).with_context(sedar_inventory_generation=True).unlink()
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
        self.sync_automated_readiness()
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
            eligible.sync_automated_readiness()
        return result


class SedarTugAssignment(models.Model):
    _inherit = "sedar.tug.assignment"

    inventory_requirement_ids = fields.One2many(
        "sedar.inventory.requirement", "tug_assignment_id", string="Onboard Inventory Requirements"
    )
    capability_status = fields.Selection(
        [("ready", "Ready"), ("blocked", "Blocked")],
        compute="_compute_integrated_readiness",
    )
    schedule_status = fields.Selection(
        [("ready", "Ready"), ("blocked", "Blocked")],
        compute="_compute_integrated_readiness",
    )
    technical_status = fields.Selection(
        [("ready", "Ready"), ("blocked", "Blocked")],
        compute="_compute_integrated_readiness",
    )
    crew_readiness_status = fields.Selection(
        [("ready", "Ready"), ("blocked", "Blocked")],
        compute="_compute_integrated_readiness",
    )
    inventory_readiness_status = fields.Selection(
        [("ready", "Onboard"), ("conditional", "Replenishment Required"), ("blocked", "Purchase Required")],
        compute="_compute_integrated_readiness",
    )
    overall_readiness_status = fields.Selection(
        [("ready", "Ready"), ("conditional", "Conditionally Ready"), ("blocked", "Blocked")],
        compute="_compute_integrated_readiness",
    )
    integrated_readiness_summary = fields.Char(compute="_compute_integrated_readiness")

    @api.depends(
        "tugboat_id",
        "tugboat_id.active",
        "tugboat_id.availability_status",
        "tugboat_id.stock_location_id",
        "order_id.tug_class_id",
        "order_id.required_bollard_pull",
        "planned_start",
        "planned_end",
        "requirement_ids.gap_count",
        "requirement_ids.compliance_issue_count",
        "inventory_requirement_ids.readiness_state",
    )
    def _compute_integrated_readiness(self):  # noqa: C901, PLR0912
        for assignment in self:
            reasons = []
            tug = assignment.tugboat_id

            capability_ready = bool(tug and tug.active)
            if assignment.order_id.tug_class_id and tug.tug_class_id != assignment.order_id.tug_class_id:
                capability_ready = False
                reasons.append("Tug class does not match")
            if assignment.order_id.required_bollard_pull and tug.bollard_pull < assignment.order_id.required_bollard_pull:
                capability_ready = False
                reasons.append("Insufficient bollard pull")
            assignment.capability_status = "ready" if capability_ready else "blocked"

            overlap = self.search_count([
                ("id", "!=", assignment.id),
                ("tugboat_id", "=", tug.id),
                ("state", "in", ["planned", "confirmed"]),
                ("planned_start", "<", assignment.planned_end),
                ("planned_end", ">", assignment.planned_start),
            ]) if tug and assignment.planned_start and assignment.planned_end else 0
            assignment.schedule_status = "blocked" if overlap else "ready"
            if overlap:
                reasons.append("Overlapping tug assignment")

            requests, drydocks = tug.sedar_technical_blockers_for_window(
                assignment.planned_start, assignment.planned_end
            ) if tug else (self.env["maintenance.request"], self.env["sedar.drydock.plan"])
            technical_ready = bool(tug) and tug.availability_status not in {"maintenance", "inactive"}
            if requests:
                reasons.append("Maintenance: %s" % ", ".join(requests.mapped("name")[:2]))
            if drydocks:
                reasons.append("Dry dock: %s" % ", ".join(drydocks.mapped("name")[:2]))
            technical_ready = technical_ready and not requests and not drydocks
            assignment.technical_status = "ready" if technical_ready else "blocked"

            manning = assignment.requirement_ids
            crew_ready = bool(manning) and not any(
                requirement.gap_count or requirement.compliance_issue_count for requirement in manning
            )
            if not crew_ready:
                reasons.append("Crew plan incomplete or noncompliant")
            assignment.crew_readiness_status = "ready" if crew_ready else "blocked"

            inventory = assignment.inventory_requirement_ids
            if tug and not tug.stock_location_id:
                inventory_status = "blocked"
                reasons.append("Tug stock location is not configured")
            elif inventory and all(line.readiness_state == "ready" for line in inventory):
                inventory_status = "ready"
            elif inventory and any(line.readiness_state == "purchase_required" for line in inventory):
                inventory_status = "blocked"
                reasons.append("Purchase required for onboard stock")
            else:
                inventory_status = "conditional"
                reasons.append("Onboard replenishment required")
            assignment.inventory_readiness_status = inventory_status

            if "blocked" in {
                assignment.capability_status,
                assignment.schedule_status,
                assignment.technical_status,
                assignment.crew_readiness_status,
                assignment.inventory_readiness_status,
            }:
                assignment.overall_readiness_status = "blocked"
            elif inventory_status == "conditional":
                assignment.overall_readiness_status = "conditional"
            else:
                assignment.overall_readiness_status = "ready"
            assignment.integrated_readiness_summary = "; ".join(reasons) or "Tug, crew, and onboard stock are ready."

    @api.model_create_multi
    def create(self, vals_list):
        assignments = super().create(vals_list)
        assignments.mapped("order_id").action_generate_inventory_requirements()
        assignments._sedar_refresh_impacted_orders()
        return assignments

    def write(self, vals):
        orders = self.mapped("order_id")
        old_tugs = self.mapped("tugboat_id")
        result = super().write(vals)
        if self.env.context.get("sedar_automated_dispatch"):
            return result
        if {"tugboat_id", "state"}.intersection(vals):
            (orders | self.mapped("order_id")).action_generate_inventory_requirements()
            self._sedar_refresh_impacted_orders(old_tugs | self.mapped("tugboat_id"))
        return result

    def unlink(self):
        orders = self.mapped("order_id")
        old_tugs = self.mapped("tugboat_id")
        result = super().unlink()
        orders.action_generate_inventory_requirements()
        self._sedar_refresh_impacted_orders(old_tugs)
        return result

    def _sedar_refresh_impacted_orders(self, tugboats=None):
        tugboats = tugboats or self.mapped("tugboat_id")
        assignments = self.env["sedar.tug.assignment"].search([
            ("tugboat_id", "in", tugboats.ids),
            ("state", "!=", "cancelled"),
        ])
        orders = assignments.mapped("order_id")
        orders.recompute_readiness()
        orders.sync_automated_readiness()
        return orders

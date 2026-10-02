from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarDrydockPlan(models.Model):
    _name = "sedar.drydock.plan"
    _description = "SEDAR Dry Dock Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc, tugboat_id"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        related="tugboat_id.company_id", store=True, index=True, readonly=True,
    )
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, ondelete="restrict", tracking=True,
        check_company=True,
    )
    planned_start = fields.Datetime(required=True, tracking=True)
    planned_end = fields.Datetime(required=True, tracking=True)
    yard_name = fields.Char(required=True)
    scope_summary = fields.Text(required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    availability_impact = fields.Selection(
        [
            ("none", "No Availability Impact"),
            ("blocking", "Blocks Tug Readiness"),
        ],
        default="blocking",
        required=True,
    )
    sedar_blocks_tug_readiness = fields.Boolean(
        compute="_compute_sedar_blocks_tug_readiness",
        store=True,
    )
    milestone_ids = fields.One2many("sedar.drydock.milestone", "plan_id", string="Milestones")
    work_order_ids = fields.One2many("maintenance.request", "sedar_drydock_plan_id", string="Work Orders")
    reset_pm_counters = fields.Boolean(
        string="Restart PM Counters on Completion", default=True,
        help="Completing this dry dock restarts every Planned Maintenance checkpoint count of the tugboat.",
    )
    release_note = fields.Text()
    released_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    released_at = fields.Datetime(readonly=True, copy=False)

    @api.depends("state", "availability_impact")
    def _compute_sedar_blocks_tug_readiness(self):
        for plan in self:
            plan.sedar_blocks_tug_readiness = (
                plan.availability_impact == "blocking" and plan.state == "in_progress"
            )

    def sedar_blocks_window(self, window_start, window_end):
        """Return whether this plan prevents operating during a requested window."""
        self.ensure_one()
        if self.availability_impact != "blocking" or self.state not in {"planned", "in_progress"}:
            return False
        if not window_start:
            return self.state == "in_progress"
        window_end = window_end or window_start
        return self.planned_start < window_end and self.planned_end > window_start

    @api.constrains("planned_start", "planned_end")
    def _check_dates(self):
        for plan in self:
            if plan.planned_end <= plan.planned_start:
                raise ValidationError("Dry dock planned end must be later than the planned start.")

    def _check_maintenance_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_marine_maintenance.group_marine_maintenance_manager"):
            raise AccessError("Only a Marine Maintenance Manager may control dry dock release.")

    def action_plan(self):
        self._check_maintenance_manager()
        self.write({"state": "planned"})
        self.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return True

    def action_start(self):
        self._check_maintenance_manager()
        self.write({"state": "in_progress"})
        self.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return True

    def action_complete(self):
        self._check_maintenance_manager()
        for plan in self:
            if not plan.release_note:
                raise UserError("Enter a dry dock release note before completion.")
            plan.write({
                "state": "completed",
                "released_by_id": self.env.user.id,
                "released_at": fields.Datetime.now(),
            })
            if plan.reset_pm_counters:
                tasks = plan.tugboat_id.maintenance_equipment_ids.sedar_pm_task_ids
                tasks._sedar_restart_cycle()
                plan.message_post(body=f"Planned Maintenance counters restarted for {len(tasks)} task(s).")
        self.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return True

    def action_cancel(self):
        self._check_maintenance_manager()
        self.write({"state": "cancelled"})
        self.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return True

    def _sedar_refresh_service_order_readiness(self, tugboats=None):
        tugboats = tugboats or self.mapped("tugboat_id")
        assignments = self.env["sedar.tug.assignment"].search([
            ("tugboat_id", "in", tugboats.ids),
            ("state", "!=", "cancelled"),
        ])
        orders = assignments.mapped("order_id")
        orders.recompute_readiness()
        orders.sync_automated_readiness()
        return orders

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        plans.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        plans._sedar_refresh_service_order_readiness()
        return plans

    def write(self, vals):
        old_tugs = self.mapped("tugboat_id")
        result = super().write(vals)
        if {"state", "availability_impact", "tugboat_id", "planned_start", "planned_end"}.intersection(vals):
            impacted_tugs = old_tugs | self.mapped("tugboat_id")
            impacted_tugs._sedar_sync_maintenance_availability()
            self._sedar_refresh_service_order_readiness(impacted_tugs)
        return result


class SedarDrydockMilestone(models.Model):
    _name = "sedar.drydock.milestone"
    _description = "SEDAR Dry Dock Milestone"
    _order = "plan_id, sequence, planned_date"
    _check_company_auto = True

    plan_id = fields.Many2one(
        "sedar.drydock.plan", required=True, ondelete="cascade", check_company=True,
    )
    company_id = fields.Many2one(
        related="plan_id.company_id", store=True, index=True, readonly=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    planned_date = fields.Datetime(required=True)
    actual_date = fields.Datetime()
    responsible_id = fields.Many2one("res.users")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
    )
    note = fields.Text()

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarDrydockPlan(models.Model):
    _name = "sedar.drydock.plan"
    _description = "SEDAR Dry Dock Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc, tugboat_id"

    name = fields.Char(required=True, tracking=True)
    tugboat_id = fields.Many2one("sedar.tugboat", required=True, ondelete="restrict", tracking=True)
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
    release_note = fields.Text()
    released_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    released_at = fields.Datetime(readonly=True, copy=False)

    @api.depends("state", "availability_impact")
    def _compute_sedar_blocks_tug_readiness(self):
        for plan in self:
            plan.sedar_blocks_tug_readiness = (
                plan.availability_impact == "blocking" and plan.state in {"planned", "in_progress"}
            )

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
        self.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return True

    def action_cancel(self):
        self._check_maintenance_manager()
        self.write({"state": "cancelled"})
        self.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        plans.mapped("tugboat_id")._sedar_sync_maintenance_availability()
        return plans

    def write(self, vals):
        old_tugs = self.mapped("tugboat_id")
        result = super().write(vals)
        if {"state", "availability_impact", "tugboat_id"}.intersection(vals):
            (old_tugs | self.mapped("tugboat_id"))._sedar_sync_maintenance_availability()
        return result


class SedarDrydockMilestone(models.Model):
    _name = "sedar.drydock.milestone"
    _description = "SEDAR Dry Dock Milestone"
    _order = "plan_id, sequence, planned_date"

    plan_id = fields.Many2one("sedar.drydock.plan", required=True, ondelete="cascade")
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

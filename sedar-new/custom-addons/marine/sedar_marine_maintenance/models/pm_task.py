from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare

from .maintenance_equipment_common import READING_PRECISION_DIGITS

ALERT_STATES = {"due", "overdue"}


class SedarPmTask(models.Model):
    """One checklist item that repeats at fixed running-hour checkpoints (300, 600, 900, ...)."""

    _name = "sedar.pm.task"
    _description = "Planned Maintenance Task"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "equipment_id, interval_hours, name"
    _check_company_auto = True

    name = fields.Char(string="Task", required=True)
    active = fields.Boolean(default=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Equipment", required=True, index=True,
        ondelete="restrict", check_company=True,
    )
    company_id = fields.Many2one(
        related="equipment_id.company_id", store=True, index=True, readonly=True
    )
    tugboat_id = fields.Many2one(
        related="equipment_id.sedar_tugboat_id", store=True, index=True, readonly=True
    )
    interval_hours = fields.Float(
        string="Every (hours)", required=True,
        help="The task falls due at every multiple of this interval: 300, 600, 900, and so on.",
    )
    warning_hours = fields.Float(
        string="Approaching Window (hours)", default=50.0,
        help="The task is shown as approaching once this few hours remain before its checkpoint.",
    )
    notes = fields.Text(string="Instructions")
    completion_ids = fields.One2many("sedar.pm.task.completion", "task_id", string="Completions")
    cycle = fields.Integer(
        default=1, readonly=True, copy=False,
        help="Checkpoint cycle. A dry dock starts a new one; earlier completions stay as history.",
    )
    cycle_start_hours = fields.Float(
        readonly=True, copy=False,
        help="Running Hours at which the current cycle started. Checkpoints count from here.",
    )

    current_hours = fields.Float(
        compute="_compute_sedar_pm_status", store=True, readonly=True,
        string="Current Running Hours",
    )
    last_checkpoint_hours = fields.Float(
        compute="_compute_sedar_pm_status", store=True, readonly=True,
        string="Last Completed Checkpoint",
    )
    next_checkpoint_hours = fields.Float(
        compute="_compute_sedar_pm_status", store=True, readonly=True,
        string="Next Checkpoint",
    )
    remaining_hours = fields.Float(
        compute="_compute_sedar_pm_status", store=True, readonly=True,
        string="Hours Remaining",
        help="Positive before the checkpoint, zero when due, and negative when overdue.",
    )
    state = fields.Selection(
        [
            ("not_due", "Not Due"),
            ("approaching", "Approaching"),
            ("due", "Due"),
            ("overdue", "Overdue"),
        ],
        compute="_compute_sedar_pm_status", store=True, readonly=True, index=True,
    )
    cycle_key = fields.Char(compute="_compute_sedar_pm_status", store=True, readonly=True, copy=False)
    alerted_cycle_key = fields.Char(readonly=True, copy=False)
    alert_assignment_state = fields.Selection(
        [("not_required", "Not Required"), ("assigned", "Assigned"), ("unassigned", "Needs Assignee")],
        string="Alert Assignment",
        compute="_compute_alert_assignment_state",
        store=True,
    )

    @api.depends(
        "interval_hours",
        "warning_hours",
        "cycle",
        "cycle_start_hours",
        "equipment_id.sedar_current_running_hours",
        "completion_ids.checkpoint_hours",
        "completion_ids.cycle",
    )
    def _compute_sedar_pm_status(self):
        for task in self:
            current = task.equipment_id.sedar_current_running_hours
            done = task.completion_ids.filtered(lambda completion: completion.cycle == task.cycle)
            last = max(done.mapped("checkpoint_hours"), default=task.cycle_start_hours)
            next_checkpoint = last + task.interval_hours
            remaining = next_checkpoint - current
            comparison = float_compare(current, next_checkpoint, precision_digits=READING_PRECISION_DIGITS)
            task.current_hours = current
            task.last_checkpoint_hours = last
            task.next_checkpoint_hours = next_checkpoint
            task.remaining_hours = remaining
            task.cycle_key = f"{task.id}:{task.cycle}:{next_checkpoint:.6f}"
            if comparison > 0:
                task.state = "overdue"
            elif comparison == 0:
                task.state = "due"
            elif remaining <= task.warning_hours:
                task.state = "approaching"
            else:
                task.state = "not_due"

    @api.depends(
        "state", "active",
        "equipment_id.technician_user_id", "equipment_id.technician_user_id.active",
        "company_id.sedar_maintenance_fallback_user_id",
        "company_id.sedar_maintenance_fallback_user_id.active",
    )
    def _compute_alert_assignment_state(self):
        for task in self:
            if not task.active or task.state not in ALERT_STATES:
                task.alert_assignment_state = "not_required"
            else:
                task.alert_assignment_state = "assigned" if task._sedar_get_alert_assignee() else "unassigned"

    @api.constrains("interval_hours", "warning_hours")
    def _check_hours(self):
        for task in self:
            if task.interval_hours <= 0:
                raise ValidationError(_("The interval must be greater than zero hours."))
            if task.warning_hours < 0:
                raise ValidationError(_("The approaching window cannot be negative."))

    def _sedar_restart_cycle(self):
        """Count checkpoints again from the current hours, as after a dry dock."""
        for task in self:
            task.sudo().write({"cycle": task.cycle + 1, "cycle_start_hours": task.current_hours})
        self._sedar_reconcile_alert()

    def _sedar_get_alert_assignee(self):
        self.ensure_one()
        candidates = self.equipment_id.technician_user_id | self.company_id.sedar_maintenance_fallback_user_id
        return candidates.filtered(
            lambda user: user.active and not user.share and self.company_id in user.company_ids
        )[:1]

    def _sedar_alert_type(self):
        return self.env.ref(
            "sedar_marine_maintenance.mail_activity_type_equipment_service_due",
            raise_if_not_found=False,
        )

    @api.private
    def sedar_open_alerts(self):
        """Open due-alert activities of these tasks."""
        activity_type = self._sedar_alert_type()
        if not activity_type:
            return self.env["mail.activity"]
        return self.env["mail.activity"].search([
            ("active", "=", True),
            ("activity_type_id", "=", activity_type.id),
            ("res_model", "=", self._name),
            ("res_id", "in", self.ids),
        ])

    def _sedar_reconcile_alert(self):
        """One activity per task checkpoint once it is due; closed when the checkpoint is completed."""
        task_ids = self.with_context(active_test=False).exists().ids
        activity_type = self._sedar_alert_type()
        if not task_ids or not activity_type:
            return
        self.env.cr.execute("SELECT id FROM sedar_pm_task WHERE id IN %s FOR UPDATE", [tuple(task_ids)])
        for task in self.with_context(active_test=False).browse(task_ids):
            task.invalidate_recordset(["state", "cycle_key", "alerted_cycle_key"])
            open_activities = task.sedar_open_alerts()
            if not task.active or task.state not in ALERT_STATES:
                if open_activities:
                    open_activities.action_feedback(feedback=_(
                        "Closed automatically because this checkpoint is no longer due."
                    ))
                if task.alerted_cycle_key:
                    task.sudo().write({"alerted_cycle_key": False})
                continue
            if task.alerted_cycle_key == task.cycle_key:
                continue
            assignee = task._sedar_get_alert_assignee()
            if not assignee:
                continue
            if open_activities:
                open_activities.action_feedback(feedback=_(
                    "Closed automatically because a newer checkpoint is now authoritative."
                ))
            self.env["mail.activity"].create({
                "activity_type_id": activity_type.id,
                "res_model_id": self.env["ir.model"]._get_id(self._name),
                "res_id": task.id,
                "user_id": assignee.id,
                "summary": _("%(task)s is %(state)s", task=task.name, state=task.state),
                "note": _(
                    "%(equipment)s has %(current).2f running hours. Checkpoint: %(checkpoint).2f hours.",
                    equipment=task.equipment_id.display_name,
                    current=task.current_hours,
                    checkpoint=task.next_checkpoint_hours,
                ),
                "date_deadline": fields.Date.context_today(task),
            })
            task.sudo().write({"alerted_cycle_key": task.cycle_key})

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._sedar_reconcile_alert()
        return tasks

    def write(self, vals):
        if {"cycle", "cycle_start_hours"}.intersection(vals) and not self.env.su:
            raise AccessError(_("The checkpoint cycle is restarted only by a dry dock."))
        result = super().write(vals)
        if {"interval_hours", "equipment_id", "active"}.intersection(vals):
            self._sedar_reconcile_alert()
        return result

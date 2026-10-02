from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

SYSTEM_FIELDS = {"checkpoint_hours", "running_hours", "done_by_id"}


class SedarPmTaskCompletion(models.Model):
    """Audit record that a task checkpoint was done, when, and by whom.

    Users always complete the task's next checkpoint; only seed data (superuser) may state its own.
    """

    _name = "sedar.pm.task.completion"
    _description = "Planned Maintenance Task Completion"
    _order = "checkpoint_hours desc, id desc"

    task_id = fields.Many2one(
        "sedar.pm.task", string="Task", required=True, index=True, ondelete="restrict"
    )
    equipment_id = fields.Many2one(related="task_id.equipment_id", store=True, index=True)
    company_id = fields.Many2one(related="task_id.company_id", store=True, index=True)
    checkpoint_hours = fields.Float(string="Checkpoint", readonly=True)
    running_hours = fields.Float(string="Running Hours When Done", readonly=True)
    done_on = fields.Date(string="Done On", required=True, default=fields.Date.context_today)
    done_by_id = fields.Many2one(
        "res.users", string="Done By", readonly=True, default=lambda self: self.env.user,
        ondelete="restrict",
    )
    remarks = fields.Text()

    _one_completion_per_checkpoint = models.Constraint(
        "unique(task_id, checkpoint_hours)",
        "This checkpoint has already been completed.",
    )

    @api.constrains("done_on")
    def _check_done_on(self):
        today = fields.Date.context_today(self)
        for completion in self:
            if completion.done_on > today:
                raise ValidationError(_("A completion cannot be dated in the future."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            task = self.env["sedar.pm.task"].browse(vals.get("task_id"))
            if not (self.env.su and "checkpoint_hours" in vals):
                if SYSTEM_FIELDS.intersection(vals) and not self.env.su:
                    raise AccessError(_("Checkpoint, hours and author are set by the system."))
                if task.state == "not_due":
                    raise UserError(_(
                        "%(task)s is not approaching its next checkpoint (%(hours).2f hours) yet.",
                        task=task.name, hours=task.next_checkpoint_hours,
                    ))
                vals.update(
                    checkpoint_hours=task.next_checkpoint_hours,
                    running_hours=task.current_hours,
                    done_by_id=self.env.user.id,
                )
        completions = super().create(vals_list)
        completions.task_id._sedar_reconcile_alert()
        return completions

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Completions are audit history and cannot be edited."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_module_uninstall(self):
        raise UserError(_("Completions are audit history and cannot be deleted."))

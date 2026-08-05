from odoo import fields, models
from odoo.exceptions import UserError


class SedarHrEmployee(models.Model):
    _inherit = "hr.employee"

    sedar_source_applicant_id = fields.Many2one(
        "hr.applicant",
        string="Source Applicant",
        copy=False,
        readonly=True,
        index=True,
        ondelete="set null",
    )
    sedar_source_vacancy_id = fields.Many2one(
        "sedar.job.vacancy",
        string="Source Vacancy",
        copy=False,
        readonly=True,
        index=True,
        ondelete="set null",
    )
    sedar_source_offer_id = fields.Many2one(
        "sedar.applicant.offer",
        string="Accepted Offer",
        copy=False,
        readonly=True,
        ondelete="set null",
    )
    sedar_source_requirement_request_id = fields.Many2one(
        "sedar.document.request",
        string="Approved ADM-5 Request",
        copy=False,
        readonly=True,
        ondelete="set null",
    )
    sedar_employment_type = fields.Selection(
        [
            ("probationary", "Probationary"),
            ("regular", "Regular"),
            ("project", "Project-Based"),
            ("contract", "Contract"),
        ],
        string="SEDAR Employment Type",
        copy=False,
        readonly=True,
    )
    sedar_planned_start_date = fields.Date(string="Planned Start Date", copy=False, readonly=True)
    sedar_onboarding_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ],
        string="SEDAR Onboarding",
        default="pending",
        copy=False,
        tracking=True,
    )
    sedar_onboarding_owner_id = fields.Many2one(
        "res.users",
        string="Onboarding Owner",
        copy=False,
        tracking=True,
        ondelete="set null",
    )
    sedar_onboarding_started_at = fields.Datetime(string="Onboarding Started At", readonly=True, copy=False)
    sedar_onboarding_completed_at = fields.Datetime(string="Onboarding Completed At", readonly=True, copy=False)
    sedar_onboarding_checklist = fields.Text(string="Onboarding Checklist", copy=False)

    def action_sedar_start_onboarding(self):
        self._sedar_ensure_onboarding_authority()
        for employee in self:
            if employee.sedar_onboarding_state == "done":
                raise UserError("Completed onboarding cannot be restarted.")
            employee.write({
                "sedar_onboarding_state": "in_progress",
                "sedar_onboarding_started_at": employee.sedar_onboarding_started_at or fields.Datetime.now(),
                "sedar_onboarding_owner_id": employee.sedar_onboarding_owner_id.id or self.env.user.id,
            })
            employee._sedar_schedule_onboarding_activity()
        return True

    def action_sedar_complete_onboarding(self):
        self._sedar_ensure_onboarding_authority()
        for employee in self:
            if employee.sedar_onboarding_state != "in_progress":
                raise UserError("Start onboarding before marking it done.")
            employee.write({
                "sedar_onboarding_state": "done",
                "sedar_onboarding_completed_at": fields.Datetime.now(),
            })
            activity_type = self.env.ref("sedar_recruitment_operations.mail_activity_employee_onboarding", raise_if_not_found=False)
            activities = employee.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)
            if activities:
                activities.action_feedback(feedback="SEDAR employee onboarding completed.")
        return True

    def _sedar_schedule_onboarding_activity(self):
        activity_type = self.env.ref("sedar_recruitment_operations.mail_activity_employee_onboarding", raise_if_not_found=False)
        if not activity_type:
            return False
        for employee in self:
            if employee.sedar_onboarding_state == "done":
                continue
            user = employee.sedar_onboarding_owner_id or self.env.user
            employee.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=user.id,
                summary="Complete SEDAR employee onboarding setup",
                note=employee.sedar_onboarding_checklist or False,
            )
        return True

    def _sedar_ensure_onboarding_authority(self):
        if not self.env.user.has_group("hr_recruitment.group_hr_recruitment_manager"):
            raise UserError("Only an HR Recruitment Manager may control employee onboarding.")
        return True

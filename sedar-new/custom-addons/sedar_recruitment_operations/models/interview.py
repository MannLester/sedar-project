from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarInterview(models.Model):
    _name = "sedar.applicant.interview"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "SEDAR Applicant Interview"
    _order = "start_datetime desc, id desc"

    name = fields.Char(required=True, default="New Applicant Interview")
    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade", index=True)
    vacancy_id = fields.Many2one("sedar.job.vacancy", related="applicant_id.sedar_vacancy_id", store=True, readonly=True)
    job_id = fields.Many2one("hr.job", related="applicant_id.job_id", store=True, readonly=True)
    interview_type = fields.Selection([
        ("initial", "Initial Interview"),
        ("technical", "Technical Interview"),
        ("final", "Final Interview"),
    ], required=True, default="initial")
    status = fields.Selection([
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("confirmed", "Applicant Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "Applicant Did Not Attend"),
        ("reschedule", "Rescheduling Requested"),
    ], required=True, default="draft", tracking=True)
    start_datetime = fields.Datetime(string="Starts", required=True)
    end_datetime = fields.Datetime(string="Ends", required=True)
    location = fields.Char()
    meeting_url = fields.Char(string="Online Meeting Link")
    coordinator_id = fields.Many2one("res.users", string="Coordinator", default=lambda self: self.env.user, required=True)
    interviewer_ids = fields.Many2many("res.users", "sedar_interview_interviewer_rel", "interview_id", "user_id", string="Interviewers")
    calendar_event_id = fields.Many2one("calendar.event", string="Calendar Event", readonly=True, copy=False, ondelete="set null")
    appraisal_request_id = fields.Many2one("sedar.document.request", string="ADM-4 Appraisal", readonly=True, copy=False, ondelete="set null")
    applicant_confirmation_note = fields.Text(string="Applicant Confirmation / Request")
    result = fields.Selection([
        ("recommended", "Recommended"),
        ("conditional", "Recommended with Conditions"),
        ("not_recommended", "Not Recommended"),
        ("pending", "Pending Decision"),
    ], string="Interview Result")
    internal_notes = fields.Text()

    @api.constrains("start_datetime", "end_datetime")
    def _check_duration(self):
        for interview in self:
            if interview.start_datetime and interview.end_datetime <= interview.start_datetime:
                raise ValidationError("The interview end time must be later than the start time.")

    @api.onchange("applicant_id")
    def _onchange_applicant_id(self):
        for interview in self:
            if interview.applicant_id:
                interview.name = "Interview - %s" % interview.applicant_id._sedar_applicant_name()

    def _interviewer_names(self):
        self.ensure_one()
        users = self.interviewer_ids or self.coordinator_id
        return ", ".join(users.mapped("name"))

    def _create_appraisal_request(self):
        self.ensure_one()
        if self.appraisal_request_id:
            return self.appraisal_request_id
        document_type = self.env.ref("sedar_document_control.document_type_adm_4")
        request = self.env["sedar.document.request"].create({
            "name": "ADM-4 Interview Appraisal - %s" % self.applicant_id.sedar_reference,
            "document_type_id": document_type.id,
            "subject_name": self.applicant_id._sedar_applicant_name(),
            "subject_reference": self.applicant_id.sedar_reference,
            "assigned_user_id": (self.interviewer_ids or self.coordinator_id)[:1].id,
            "applicant_id": self.applicant_id.id,
            "interview_id": self.id,
            "sedar_request_purpose": "interview_appraisal",
            "applicant_visible": False,
            "notes": "Complete this ADM-4 appraisal for the scheduled interview.",
        })
        values = {
            "applicant_name": {"value_text": self.applicant_id._sedar_applicant_name()},
            "interview_date": {"value_date": fields.Date.to_date(self.start_datetime)},
            "position_applied": {"value_text": self.applicant_id._sedar_position_name()},
            "interviewer": {"value_text": self._interviewer_names()},
        }
        for value in request.value_ids:
            value.write(values.get(value.field_id.technical_name, {}))
        self.appraisal_request_id = request.id
        return request

    def _sync_appraisal_values(self):
        for interview in self.filtered("appraisal_request_id"):
            values = {
                "applicant_name": {"value_text": interview.applicant_id._sedar_applicant_name()},
                "interview_date": {"value_date": fields.Date.to_date(interview.start_datetime)},
                "position_applied": {"value_text": interview.applicant_id._sedar_position_name()},
                "interviewer": {"value_text": interview._interviewer_names()},
            }
            for value in interview.appraisal_request_id.value_ids:
                update = values.get(value.field_id.technical_name)
                if update:
                    value.write(update)

    def _create_or_update_calendar_event(self):
        self.ensure_one()
        attendees = (self.interviewer_ids | self.coordinator_id).mapped("partner_id")
        applicant_partner = self.applicant_id.partner_id
        if applicant_partner:
            attendees |= applicant_partner
        vals = {
            "name": self.name,
            "start": self.start_datetime,
            "stop": self.end_datetime,
            "allday": False,
            "user_id": self.coordinator_id.id,
            "partner_ids": [(6, 0, attendees.ids)],
            "location": self.location,
            "description": self._calendar_description(),
        }
        if self.calendar_event_id:
            self.calendar_event_id.write(vals)
        else:
            self.calendar_event_id = self.env["calendar.event"].create(vals).id
        return self.calendar_event_id

    def _calendar_description(self):
        self.ensure_one()
        lines = [
            "SEDAR applicant interview",
            "Application: %s" % self.applicant_id.sedar_reference,
            "Applicant: %s" % self.applicant_id._sedar_applicant_name(),
        ]
        if self.meeting_url:
            lines.append("Meeting link: %s" % self.meeting_url)
        return "\n".join(lines)

    def action_schedule(self):
        for interview in self:
            if interview.applicant_id.sedar_public_status not in ("shortlisted", "interview"):
                raise UserError("Only a qualified applicant can be scheduled for an interview.")
            if not interview.interviewer_ids:
                raise UserError("Assign at least one interviewer before scheduling.")
            interview._create_or_update_calendar_event()
            interview._create_appraisal_request()
            interview._sync_appraisal_values()
            interview.write({"status": "scheduled"})
            interview.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_interview_scheduled",
                next_action="Attend scheduled interview",
                next_action_date=fields.Date.to_date(interview.start_datetime),
                message="Your interview has been scheduled. Please review the date, time, and instructions.",
            )
        return True

    def action_update_schedule(self):
        for interview in self:
            if interview.status not in ("scheduled", "confirmed", "reschedule"):
                raise UserError("Only scheduled interviews can be updated.")
            if not interview.interviewer_ids:
                raise UserError("Assign at least one interviewer before updating the schedule.")
            interview._create_or_update_calendar_event()
            interview._sync_appraisal_values()
            interview.write({"status": "scheduled"})
            interview.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_interview_scheduled",
                next_action="Attend updated interview schedule",
                next_action_date=fields.Date.to_date(interview.start_datetime),
                message="Your interview schedule has been updated. Please review the latest date, time, and instructions.",
            )
        return True

    def action_confirm_applicant(self):
        for interview in self:
            interview.write({"status": "confirmed", "applicant_confirmation_note": False})
            interview.applicant_id._create_portal_event(
                "interview",
                "Interview Confirmed",
                "Your interview attendance has been confirmed.",
            )
        return True

    def action_request_reschedule(self):
        for interview in self:
            interview.write({"status": "reschedule"})
            interview.applicant_id._create_portal_event(
                "interview",
                "Interview Reschedule Requested",
                "Your reschedule request has been sent to HR.",
            )
        return True

    def action_complete(self):
        for interview in self:
            if not interview.appraisal_request_id or interview.appraisal_request_id.state not in ("submitted", "reviewed", "approved"):
                raise UserError("Submit the ADM-4 appraisal before completing the interview.")
            interview.write({"status": "completed"})
            interview.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_interview_completed",
                next_action="Review interview appraisal",
                message="Your interview has been completed and is under HR review.",
            )
        return True

    def action_cancel(self):
        self.write({"status": "cancelled"})
        return True


class SedarDocumentRequestInterview(models.Model):
    _inherit = "sedar.document.request"

    applicant_id = fields.Many2one("hr.applicant", string="Applicant", ondelete="cascade", index=True)
    interview_id = fields.Many2one("sedar.applicant.interview", string="Interview", ondelete="set null", index=True)
    sedar_request_purpose = fields.Selection([
        ("interview_appraisal", "Interview Appraisal"),
        ("employment_requirements", "Employment Requirements"),
        ("background_check", "Background Check"),
        ("orientation", "Orientation"),
    ], string="SEDAR Purpose")
    applicant_visible = fields.Boolean(string="Visible to Applicant", default=False)
    applicant_submission_note = fields.Text(string="Applicant Submission Note")

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .hsse_common import SEVERITIES, _check_hsse_manager


class SedarHsseCorrectiveAction(models.Model):
    _name = "sedar.hsse.corrective.action"
    _description = "HSSE Corrective Action"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_date, severity desc, id"

    name = fields.Char(required=True)
    incident_id = fields.Many2one("sedar.hsse.incident", ondelete="cascade")
    inspection_finding_id = fields.Many2one("sedar.hsse.inspection.finding", ondelete="cascade")
    risk_assessment_id = fields.Many2one("sedar.hsse.risk.assessment", ondelete="cascade")
    assigned_user_id = fields.Many2one("res.users", required=True)
    due_date = fields.Date(required=True)
    severity = fields.Selection(SEVERITIES, required=True, default="medium")
    critical_control = fields.Boolean()
    description = fields.Text(required=True)
    completion_note = fields.Text()
    evidence = fields.Binary(attachment=True)
    evidence_filename = fields.Char()
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    verified_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    verified_at = fields.Datetime(readonly=True, copy=False)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", store=True)
    operational_exception = fields.Boolean(compute="_compute_operational_exception", store=True)
    state = fields.Selection(
        [("open", "Open"), ("done", "Done"), ("verified", "Verified"), ("cancelled", "Cancelled")],
        default="open",
        required=True,
        tracking=True,
    )

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for action in self:
            action.is_overdue = bool(action.due_date and action.due_date < today and action.state == "open")

    @api.depends("critical_control", "state")
    def _compute_operational_exception(self):
        for action in self:
            action.operational_exception = action.critical_control and action.state not in {"verified", "cancelled"}

    @api.constrains("incident_id", "inspection_finding_id", "risk_assessment_id")
    def _check_single_source(self):
        for action in self:
            source_count = sum(bool(source) for source in [
                action.incident_id,
                action.inspection_finding_id,
                action.risk_assessment_id,
            ])
            if source_count > 1:
                raise ValidationError("A corrective action can be linked to only one HSSE source record.")

    def action_mark_done(self):
        for action in self:
            if not action.completion_note:
                raise UserError("Enter a completion note before marking the corrective action done.")
            action.write({
                "state": "done",
                "completed_by_id": self.env.user.id,
                "completed_at": fields.Datetime.now(),
            })
        return True

    def action_verify(self):
        _check_hsse_manager(self)
        for action in self:
            if action.state != "done":
                raise UserError("Only completed corrective actions can be verified.")
            action.write({
                "state": "verified",
                "verified_by_id": self.env.user.id,
                "verified_at": fields.Datetime.now(),
            })
        return True


class SedarHsseMeeting(models.Model):
    _name = "sedar.hsse.meeting"
    _description = "HSSE Safety Meeting"
    _inherit = ["mail.thread", "mail.activity.mixin", "sedar.hsse.source.mixin"]
    _order = "meeting_datetime desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    meeting_type = fields.Selection(
        [("toolbox", "Toolbox Meeting"), ("safety", "Safety Meeting"), ("committee", "HSSE Committee")],
        default="toolbox",
        required=True,
    )
    meeting_datetime = fields.Datetime(required=True, default=fields.Datetime.now)
    facilitator_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    attendee_employee_ids = fields.Many2many("hr.employee", string="Employee Attendees")
    topic = fields.Char(required=True)
    minutes = fields.Text(required=True)
    corrective_action_ids = fields.One2many("sedar.hsse.corrective.action", "meeting_id")

    @api.model_create_multi
    def create(self, vals_list):
        meetings = super().create(vals_list)
        for meeting in meetings:
            if meeting.name == "New":
                meeting.name = self.env["ir.sequence"].next_by_code("sedar.hsse.meeting") or "New"
        return meetings


class SedarHsseTrainingRecord(models.Model):
    _name = "sedar.hsse.training.record"
    _description = "HSSE Training Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "completion_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    course_name = fields.Char(required=True)
    training_type = fields.Selection(
        [("orientation", "Orientation"), ("permit", "Permit"), ("emergency", "Emergency"), ("environmental", "Environmental"), ("other", "Other")],
        default="orientation",
        required=True,
    )
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    crew_profile_id = fields.Many2one("sedar.crew.profile", ondelete="set null")
    completion_date = fields.Date(required=True, default=fields.Date.context_today)
    expiry_date = fields.Date()
    document_request_id = fields.Many2one("sedar.document.request", string="Training Evidence", ondelete="set null")
    readiness_applicable = fields.Boolean(help="Marks training that may later be included in deployment readiness.")
    is_expired = fields.Boolean(compute="_compute_is_expired", store=True)
    state = fields.Selection([("completed", "Completed"), ("expired", "Expired"), ("void", "Void")], compute="_compute_is_expired", store=True, readonly=False)
    note = fields.Text()

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_expired = bool(record.expiry_date and record.expiry_date < today)
            if record.state != "void":
                record.state = "expired" if record.is_expired else "completed"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == "New":
                record.name = self.env["ir.sequence"].next_by_code("sedar.hsse.training.record") or "New"
        return records


class SedarHsseCorrectiveActionMeetingLink(models.Model):
    _inherit = "sedar.hsse.corrective.action"

    meeting_id = fields.Many2one("sedar.hsse.meeting", ondelete="cascade")


class SedarMarineServiceOrderHsse(models.Model):
    _inherit = "sedar.marine.service.order"

    hsse_exception_count = fields.Integer(compute="_compute_hsse_exceptions")
    hsse_exception_summary = fields.Char(compute="_compute_hsse_exceptions")

    def _compute_hsse_exceptions(self):
        for order in self:
            permits = self.env["sedar.hsse.permit"].search([
                ("service_order_id", "=", order.id),
                ("operational_exception", "=", True),
            ])
            actions = self.env["sedar.hsse.corrective.action"].search([
                ("operational_exception", "=", True),
                "|",
                ("incident_id.service_order_id", "=", order.id),
                ("risk_assessment_id.service_order_id", "=", order.id),
            ])
            order.hsse_exception_count = len(permits) + len(actions)
            summary = []
            if permits:
                summary.append("%s expired required permit(s)" % len(permits))
            if actions:
                summary.append("%s unresolved critical HSSE action(s)" % len(actions))
            order.hsse_exception_summary = "; ".join(summary)


class SedarTugboatHsse(models.Model):
    _inherit = "sedar.tugboat"

    hsse_exception_count = fields.Integer(compute="_compute_hsse_exceptions")
    hsse_exception_summary = fields.Char(compute="_compute_hsse_exceptions")

    def _compute_hsse_exceptions(self):
        for tugboat in self:
            permits = self.env["sedar.hsse.permit"].search([
                ("tugboat_id", "=", tugboat.id),
                ("operational_exception", "=", True),
            ])
            actions = self.env["sedar.hsse.corrective.action"].search([
                ("operational_exception", "=", True),
                "|",
                ("incident_id.tugboat_id", "=", tugboat.id),
                ("risk_assessment_id.tugboat_id", "=", tugboat.id),
            ])
            tugboat.hsse_exception_count = len(permits) + len(actions)
            summary = []
            if permits:
                summary.append("%s expired required permit(s)" % len(permits))
            if actions:
                summary.append("%s unresolved critical HSSE action(s)" % len(actions))
            tugboat.hsse_exception_summary = "; ".join(summary)

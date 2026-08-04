from odoo import api, fields, models
from odoo.exceptions import UserError


class SedarApplicantStageHistory(models.Model):
    _name = "sedar.applicant.stage.history"
    _description = "SEDAR Applicant Stage History"
    _order = "changed_at desc, id desc"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade", index=True)
    previous_stage_id = fields.Many2one("hr.recruitment.stage", string="Previous Stage", ondelete="set null")
    new_stage_id = fields.Many2one("hr.recruitment.stage", string="New Stage", required=True, ondelete="restrict")
    changed_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="restrict")
    changed_at = fields.Datetime(required=True, default=fields.Datetime.now)
    reason = fields.Text()
    applicant_message = fields.Text(string="Applicant Message")


class SedarApplicantOperations(models.Model):
    _inherit = "hr.applicant"

    sedar_recruiter_assigned_at = fields.Datetime(string="Recruiter Assigned At", readonly=True, copy=False)
    sedar_review_deadline = fields.Date(string="Review Deadline", tracking=True)
    sedar_next_action_date = fields.Date(string="Next Action Date", tracking=True)
    sedar_next_action = fields.Char(string="Next HR Action", tracking=True)
    sedar_rejection_reason = fields.Text(string="Rejection Reason", tracking=True)
    sedar_withdrawal_reason = fields.Text(string="Withdrawal Reason", tracking=True)
    sedar_stage_history_ids = fields.One2many("sedar.applicant.stage.history", "applicant_id", string="Stage History")
    sedar_interview_ids = fields.One2many("sedar.applicant.interview", "applicant_id", string="Interviews")
    sedar_requirement_request_ids = fields.One2many("sedar.document.request", "applicant_id", string="Requirement Requests")
    sedar_is_overdue = fields.Boolean(compute="_compute_sedar_is_overdue", search="_search_sedar_is_overdue")

    @api.depends("sedar_next_action_date")
    def _compute_sedar_is_overdue(self):
        today = fields.Date.context_today(self)
        for applicant in self:
            applicant.sedar_is_overdue = bool(applicant.sedar_next_action_date and applicant.sedar_next_action_date < today)

    @api.model
    def _search_sedar_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [("sedar_next_action_date", "<", today)]
        return domain if (operator == "=" and value) or (operator == "!=" and not value) else ["!"] + domain

    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        for applicant in applicants:
            if applicant.stage_id:
                applicant._create_stage_history(None, applicant.stage_id, "Application created")
        return applicants

    def write(self, vals):
        vals = dict(vals)
        new_stage = self.env["hr.recruitment.stage"].browse(vals["stage_id"]).exists() if vals.get("stage_id") else self.env["hr.recruitment.stage"]
        if new_stage and new_stage.sedar_public_status and "sedar_public_status" not in vals:
            vals["sedar_public_status"] = new_stage.sedar_public_status
        previous_stages = {applicant.id: applicant.stage_id for applicant in self} if "stage_id" in vals else {}
        result = super().write(vals)
        if "user_id" in vals:
            self.write({"sedar_recruiter_assigned_at": fields.Datetime.now() if vals.get("user_id") else False})
        if "stage_id" in vals:
            for applicant in self:
                previous_stage = previous_stages.get(applicant.id)
                if previous_stage != applicant.stage_id:
                    applicant._create_stage_history(previous_stage, applicant.stage_id, applicant.sedar_next_action or "Stage changed")
        return result

    def _create_stage_history(self, previous_stage, new_stage, reason=None):
        self.ensure_one()
        if not new_stage:
            return
        self.env["sedar.applicant.stage.history"].sudo().create({
            "applicant_id": self.id,
            "previous_stage_id": previous_stage.id if previous_stage else False,
            "new_stage_id": new_stage.id,
            "reason": reason,
            "applicant_message": self.sedar_public_message,
        })

    def _move_to_sedar_stage(self, stage_xmlid, next_action=False, next_action_date=False, message=False, action_required=False):
        stage = self.env.ref(stage_xmlid)
        for applicant in self:
            applicant.write({
                "stage_id": stage.id,
                "sedar_next_action": next_action,
                "sedar_next_action_date": next_action_date,
                "sedar_public_message": message or stage.sedar_public_message,
                "sedar_action_required": action_required,
                "sedar_action_instructions": message if action_required else False,
            })
        return True

    def action_sedar_start_review(self):
        return self._move_to_sedar_stage(
            "sedar_recruitment_operations.stage_under_review",
            next_action="Complete initial application review",
            message="HR is reviewing your application and submitted information.",
        )

    def action_sedar_qualify(self):
        return self._move_to_sedar_stage(
            "sedar_recruitment_operations.stage_qualified",
            next_action="Schedule applicant interview",
            message="Your application passed the initial review. SEDAR will contact you regarding the next step.",
        )

    def action_sedar_request_clarification(self):
        return self._move_to_sedar_stage(
            "sedar_recruitment_operations.stage_clarification",
            next_action="Wait for applicant clarification",
            message=self[:1].sedar_action_instructions or "Please provide the additional information requested by HR.",
            action_required=True,
        )

    def action_sedar_reject(self):
        for applicant in self:
            if not applicant.sedar_rejection_reason:
                raise UserError("Enter a rejection reason before rejecting the application.")
        return self._move_to_sedar_stage(
            "sedar_recruitment_operations.stage_rejected",
            next_action=False,
            message="Thank you for your application. SEDAR has completed its review.",
        )

    def action_sedar_clear_action(self):
        self.write({"sedar_next_action": False, "sedar_next_action_date": False})
        return True

    def action_sedar_request_employment_requirements(self):
        for applicant in self:
            if applicant.sedar_public_status not in ("final_review", "requirements", "offer"):
                raise UserError("Employment requirements can only be requested after the interview is completed.")
            request = applicant._get_or_create_requirement_request()
            if request.state == "draft":
                request.action_start()
            applicant._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_requirements_requested",
                next_action="Wait for applicant employment requirements",
                next_action_date=request.due_date,
                message="Please submit your employment requirements in the applicant dashboard.",
                action_required=True,
            )
        return True

    def action_sedar_verify_employment_requirements(self):
        for applicant in self:
            request = applicant.sedar_requirement_request_ids.filtered(
                lambda item: item.sedar_request_purpose == "employment_requirements"
            )[:1]
            if not request or request.state not in ("submitted", "reviewed", "approved"):
                raise UserError("The ADM-5 employment requirements request must be submitted before verification.")
            if request.state == "submitted":
                request.action_review()
            if request.state == "reviewed":
                request.action_approve()
            applicant._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_requirements_verified",
                next_action="Prepare employment offer / onboarding",
                message="Your employment requirements have been verified by SEDAR HR.",
            )
        return True

    def action_sedar_create_employee_profile(self):
        action = False
        for applicant in self:
            if applicant.employee_id:
                action = applicant.action_open_employee()
                continue
            if applicant.sedar_public_status != "offer":
                raise UserError("Create the employee profile only after requirements are verified.")
            request = applicant.sedar_requirement_request_ids.filtered(
                lambda item: item.sedar_request_purpose == "employment_requirements"
            )[:1]
            if not request or request.state != "approved":
                raise UserError("Approve the ADM-5 employment requirements before creating the employee profile.")
            action = applicant.create_employee_from_applicant()
            applicant._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_employee_created",
                next_action="Complete employee onboarding setup",
                message="Your employee profile has been created. SEDAR HR will complete the remaining onboarding setup.",
            )
        return action or True

    def _get_or_create_requirement_request(self):
        self.ensure_one()
        existing = self.sedar_requirement_request_ids.filtered(
            lambda request: request.sedar_request_purpose == "employment_requirements" and request.state not in ("rejected",)
        )[:1]
        if existing:
            return existing
        document_type = self.env.ref("sedar_document_control.document_type_adm_5")
        due_date = fields.Date.add(fields.Date.context_today(self), days=7)
        request = self.env["sedar.document.request"].create({
            "name": "ADM-5 Employment Requirements - %s" % self.sedar_reference,
            "document_type_id": document_type.id,
            "subject_name": self.partner_name or self.name,
            "subject_reference": self.sedar_reference,
            "assigned_user_id": self.user_id.id or self.env.user.id,
            "due_date": due_date,
            "applicant_id": self.id,
            "sedar_request_purpose": "employment_requirements",
            "applicant_visible": True,
            "notes": "Applicant must upload employment requirement files listed in ADM-5.",
        })
        values = {
            "employee_name": {"value_text": self.partner_name or self.name},
            "position": {"value_text": self.sedar_vacancy_id.website_title or self.job_id.name or ""},
            "list_given_on": {"value_date": fields.Date.context_today(self)},
            "needed_on": {"value_date": due_date},
            "requirement_checklist": {"value_text": "NBI Clearance; SSS E1/E4; ID; TIN ID; Transcript of Record; Medical Certificate; Employment Certificate; 2 Passport size pictures; Community Tax Certificate; Birth Certificate; Police Clearance; Barangay Clearance; Proof of SSS, PhilHealth and Pag-IBIG from most recent company."},
        }
        for value in request.value_ids:
            update = values.get(value.field_id.technical_name)
            if update:
                value.write(update)
        return request

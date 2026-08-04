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
    sedar_offer_ids = fields.One2many("sedar.applicant.offer", "applicant_id", string="Hiring Decisions and Offers")
    sedar_current_offer_id = fields.Many2one(
        "sedar.applicant.offer",
        compute="_compute_sedar_current_offer",
        string="Current Offer",
    )
    sedar_is_overdue = fields.Boolean(compute="_compute_sedar_is_overdue", search="_search_sedar_is_overdue")

    @api.depends("sedar_next_action_date")
    def _compute_sedar_is_overdue(self):
        today = fields.Date.context_today(self)
        for applicant in self:
            applicant.sedar_is_overdue = bool(applicant.sedar_next_action_date and applicant.sedar_next_action_date < today)

    def _compute_sedar_current_offer(self):
        for applicant in self:
            applicant.sedar_current_offer_id = applicant.sedar_offer_ids.filtered(
                lambda offer: offer.state in ("issued", "accepted")
            )[:1]

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

    def action_sedar_create_recruitment_controls(self):
        for applicant in self:
            if applicant.sedar_public_status != "final_review":
                raise UserError("Create background and orientation controls only after the interview is completed.")
            if not applicant._sedar_requires_recruitment_controls():
                raise UserError("This demo requires background and orientation controls only for marine crew applicants.")
            requests = applicant._get_or_create_recruitment_control_requests()
            requests.filtered(lambda request: request.state == "draft").action_start()
            applicant.write({
                "sedar_next_action": "Complete background inquiry and company orientation",
                "sedar_next_action_date": min(requests.mapped("due_date")) if requests else False,
                "sedar_public_message": "Your interview is complete. SEDAR HR is completing internal pre-employment checks.",
                "sedar_action_required": False,
                "sedar_action_instructions": False,
            })
        return True

    def action_sedar_verify_recruitment_controls(self):
        for applicant in self:
            applicant._ensure_recruitment_controls_approved(auto_approve=True)
            applicant.write({
                "sedar_next_action": "Issue hiring decision / offer",
                "sedar_next_action_date": fields.Date.add(fields.Date.context_today(applicant), days=2),
                "sedar_public_message": "SEDAR HR has completed the internal pre-employment checks for your application.",
                "sedar_action_required": False,
                "sedar_action_instructions": False,
            })
        return True

    def action_sedar_create_offer(self):
        action = False
        for applicant in self:
            if applicant.sedar_public_status != "final_review":
                raise UserError("Create an offer only after the interview and HR controls are completed.")
            applicant._ensure_recruitment_controls_approved()
            offer = applicant._get_or_create_offer()
            action = {
                "type": "ir.actions.act_window",
                "name": "Hiring Decision / Offer",
                "res_model": "sedar.applicant.offer",
                "res_id": offer.id,
                "view_mode": "form",
                "target": "current",
            }
        return action or True

    def action_sedar_request_employment_requirements(self):
        for applicant in self:
            if applicant.sedar_public_status not in ("final_review", "requirements", "offer"):
                raise UserError("Employment requirements can only be requested after the interview is completed.")
            applicant._ensure_recruitment_controls_approved()
            applicant._ensure_offer_accepted()
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
            applicant._ensure_offer_accepted()
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
            "subject_name": self._sedar_applicant_name(),
            "subject_reference": self.sedar_reference,
            "assigned_user_id": self.user_id.id or self.env.user.id,
            "due_date": due_date,
            "applicant_id": self.id,
            "sedar_request_purpose": "employment_requirements",
            "applicant_visible": True,
            "notes": "Applicant must upload employment requirement files listed in ADM-5.",
        })
        values = {
            "employee_name": {"value_text": self._sedar_applicant_name()},
            "position": {"value_text": self._sedar_position_name()},
            "list_given_on": {"value_date": fields.Date.context_today(self)},
            "needed_on": {"value_date": due_date},
            "requirement_checklist": {"value_text": "NBI Clearance; SSS E1/E4; ID; TIN ID; Transcript of Record; Medical Certificate; Employment Certificate; 2 Passport size pictures; Community Tax Certificate; Birth Certificate; Police Clearance; Barangay Clearance; Proof of SSS, PhilHealth and Pag-IBIG from most recent company."},
        }
        for value in request.value_ids:
            update = values.get(value.field_id.technical_name)
            if update:
                value.write(update)
        return request

    def _get_or_create_offer(self):
        self.ensure_one()
        existing = self.sedar_offer_ids.filtered(lambda offer: offer.state in ("draft", "issued", "accepted"))[:1]
        if existing:
            return existing
        today = fields.Date.context_today(self)
        return self.env["sedar.applicant.offer"].create({
            "applicant_id": self.id,
            "offered_position": self._sedar_position_name(),
            "employment_type": "probationary",
            "proposed_start_date": fields.Date.add(today, days=14),
            "expiry_date": fields.Date.add(today, days=7),
            "offer_summary": "Demo offer for the listed position, subject to SEDAR HR completion of employment requirements and onboarding.",
        })

    def _ensure_offer_accepted(self):
        for applicant in self:
            offer = applicant.sedar_offer_ids.filtered(lambda item: item.state == "accepted")[:1]
            if not offer:
                raise UserError("An accepted hiring offer is required before requesting ADM-5 employment requirements or creating an employee profile.")
        return True

    def _sedar_applicant_name(self):
        self.ensure_one()
        return self.partner_name or self.display_name

    def _sedar_position_name(self):
        self.ensure_one()
        return self.sedar_vacancy_id.website_title or self.job_id.name or ""

    def _sedar_requires_recruitment_controls(self):
        self.ensure_one()
        return bool(self.sedar_vacancy_id.crew_rank_id)

    def _sedar_recruitment_control_purposes(self):
        self.ensure_one()
        return ("background_check", "orientation") if self._sedar_requires_recruitment_controls() else ()

    def _sedar_recruitment_control_requests(self):
        self.ensure_one()
        return self.sedar_requirement_request_ids.filtered(
            lambda request: request.sedar_request_purpose in self._sedar_recruitment_control_purposes()
            and request.state != "rejected"
        )

    def _get_or_create_recruitment_control_requests(self):
        self.ensure_one()
        requests = self.env["sedar.document.request"]
        for purpose in self._sedar_recruitment_control_purposes():
            requests |= self._get_or_create_recruitment_control_request(purpose)
        return requests

    def _get_or_create_recruitment_control_request(self, purpose):
        self.ensure_one()
        existing = self.sedar_requirement_request_ids.filtered(
            lambda request: request.sedar_request_purpose == purpose and request.state != "rejected"
        )[:1]
        if existing:
            return existing
        if purpose == "background_check":
            document_type = self.env.ref("sedar_document_control.document_type_adm_4a")
            due_date = fields.Date.add(fields.Date.context_today(self), days=5)
            request = self.env["sedar.document.request"].create({
                "name": "ADM-4A Background Inquiry - %s" % self.sedar_reference,
                "document_type_id": document_type.id,
                "subject_name": self._sedar_applicant_name(),
                "subject_reference": self.sedar_reference,
                "assigned_user_id": self.user_id.id or self.env.user.id,
                "due_date": due_date,
                "applicant_id": self.id,
                "sedar_request_purpose": "background_check",
                "applicant_visible": False,
                "notes": "Confidential HR background inquiry for a marine crew applicant. Applicant portal must not expose the detailed response.",
            })
            values = {
                "correspondence_to": {"value_text": "Previous Employer / Manning Agency"},
                "inquiry_date": {"value_date": fields.Date.context_today(self)},
                "attention_to": {"value_text": "HR / Crewing Records"},
                "reference": {"value_text": self.sedar_reference},
                "applicant_name": {"value_text": self._sedar_applicant_name()},
                "last_vessel": {"value_text": "Previous vessel or tug assignment, if confirmed by HR"},
                "position": {"value_text": self._sedar_position_name()},
                "evaluation_results": {"value_text": "Pending evaluator response for Ability, Conduct / Attitude, Responsibility, Technical Competence, Health, and Overall Assessment."},
                "general_remarks": {"value_text": "Demo workflow: HR records confidential background findings here before approval."},
            }
        elif purpose == "orientation":
            document_type = self.env.ref("sedar_document_control.document_type_cm_053")
            due_date = fields.Date.add(fields.Date.context_today(self), days=3)
            request = self.env["sedar.document.request"].create({
                "name": "CM-053 Company Orientation - %s" % self.sedar_reference,
                "document_type_id": document_type.id,
                "subject_name": self._sedar_applicant_name(),
                "subject_reference": self.sedar_reference,
                "assigned_user_id": self.user_id.id or self.env.user.id,
                "due_date": due_date,
                "applicant_id": self.id,
                "sedar_request_purpose": "orientation",
                "applicant_visible": False,
                "notes": "Internal HR orientation control for company policies and ship crew safety orientation.",
            })
            values = {
                "orientation_date": {"value_date": fields.Date.context_today(self)},
                "applicant_name": {"value_text": self._sedar_applicant_name()},
                "position_applied": {"value_text": self._sedar_position_name()},
                "orientation_checklist": {"value_text": "ISM / ISO Orientation: Pending\nMission/Vision/Quality Policy: Pending\nJob Description: Pending\nCompany Rules & Regulation: Pending\nDisciplinary Action: Pending\nDrug-Free Workplace: Pending\nDuties & Responsibilities: Pending\nSafety On Board (Operation/Maintenance/Emergency): Pending"},
            }
        else:
            raise UserError("Unsupported recruitment control purpose: %s" % purpose)
        for value in request.value_ids:
            update = values.get(value.field_id.technical_name)
            if update:
                value.write(update)
        return request

    def _ensure_recruitment_controls_approved(self, auto_approve=False):
        for applicant in self:
            purposes = applicant._sedar_recruitment_control_purposes()
            if not purposes:
                continue
            requests = applicant._sedar_recruitment_control_requests()
            found = set(requests.mapped("sedar_request_purpose"))
            missing = sorted(set(purposes) - found)
            if missing:
                raise UserError("Create and approve ADM-4A Background Inquiry and Company Interview Orientation before requesting ADM-5 employment requirements.")
            if auto_approve:
                for request in requests:
                    if request.state in ("draft", "in_progress"):
                        raise UserError("Submit the ADM-4A and Company Interview Orientation requests before HR approval.")
                    if request.state == "submitted":
                        request.action_review()
                    if request.state == "reviewed":
                        request.action_approve()
            not_approved = requests.filtered(lambda request: request.state != "approved")
            if not_approved:
                raise UserError("Approve ADM-4A Background Inquiry and Company Interview Orientation before requesting ADM-5 employment requirements.")
        return True

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarApplicantOffer(models.Model):
    _name = "sedar.applicant.offer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "SEDAR Applicant Hiring Decision and Offer"
    _order = "issued_at desc, id desc"

    name = fields.Char(required=True, default="New Applicant Offer")
    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade", index=True)
    vacancy_id = fields.Many2one("sedar.job.vacancy", related="applicant_id.sedar_vacancy_id", store=True, readonly=True)
    job_id = fields.Many2one("hr.job", related="applicant_id.job_id", store=True, readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("withdrawn", "Withdrawn"),
        ("expired", "Expired"),
    ], required=True, default="draft", tracking=True)
    decision = fields.Selection([
        ("hire", "Hire"),
        ("conditional_hire", "Conditional Hire"),
        ("reject", "Do Not Hire"),
    ], required=True, default="hire", tracking=True)
    decision_reason = fields.Text(string="Internal Decision Rationale")
    offered_position = fields.Char(required=True)
    employment_type = fields.Selection([
        ("probationary", "Probationary"),
        ("regular", "Regular"),
        ("project", "Project-Based"),
        ("contract", "Contract"),
    ], required=True, default="probationary")
    proposed_start_date = fields.Date(required=True)
    expiry_date = fields.Date(required=True)
    offer_summary = fields.Text(required=True)
    issued_by_id = fields.Many2one("res.users", string="Issued By", readonly=True, copy=False, ondelete="restrict")
    issued_at = fields.Datetime(string="Issued At", readonly=True, copy=False)
    accepted_at = fields.Datetime(string="Accepted At", readonly=True, copy=False)
    accepted_by_id = fields.Many2one("res.users", string="Accepted By", readonly=True, copy=False, ondelete="restrict")
    acceptance_source = fields.Selection(
        [
            ("portal", "Applicant Portal"),
            ("internal_hr_confirmation", "Internal HR Confirmation"),
        ],
        string="Acceptance Source",
        readonly=True,
        copy=False,
    )
    declined_at = fields.Datetime(string="Declined At", readonly=True, copy=False)
    applicant_response_note = fields.Text(string="Applicant Response Note")

    @api.constrains("proposed_start_date", "expiry_date")
    def _check_offer_dates(self):
        for offer in self:
            if offer.proposed_start_date and offer.expiry_date and offer.expiry_date < fields.Date.context_today(offer):
                raise ValidationError("The offer expiry date cannot be in the past.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("applicant_id") and vals.get("name") in (None, "New Applicant Offer"):
                applicant = self.env["hr.applicant"].browse(vals["applicant_id"])
                vals["name"] = "Offer - %s" % (applicant.sedar_reference or applicant.display_name)
        return super().create(vals_list)

    def action_issue(self):
        self._ensure_offer_decision_authority()
        for offer in self:
            if offer.state != "draft":
                raise UserError("Only draft offers can be issued.")
            if offer.decision == "reject":
                raise UserError("Use the applicant rejection workflow for a do-not-hire decision.")
            offer.applicant_id._ensure_recruitment_controls_approved()
            other_active = offer.applicant_id.sedar_offer_ids.filtered(
                lambda item: item.id != offer.id and item.state in ("issued", "accepted")
            )
            if other_active:
                raise UserError("Withdraw the active offer before issuing another one.")
            offer.write({
                "state": "issued",
                "issued_by_id": self.env.user.id,
                "issued_at": fields.Datetime.now(),
            })
            offer.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_offer_issued",
                next_action="Wait for applicant offer response",
                next_action_date=offer.expiry_date,
                message="SEDAR has issued an employment offer. Please review and respond in your applicant dashboard.",
                action_required=True,
            )
        return True

    def action_accept(self):
        self._ensure_offer_decision_authority()
        return self._action_accept_with_audit(self.env.user, "internal_hr_confirmation")

    def action_accept_from_portal(self, response_user):
        if not response_user or response_user._is_public():
            raise UserError("A signed-in applicant portal user is required to accept an offer.")
        return self._action_accept_with_audit(response_user, "portal")

    def _action_accept_with_audit(self, response_user, source):
        for offer in self:
            if offer.state != "issued":
                raise UserError("Only an issued offer can be accepted.")
            offer.write({
                "state": "accepted",
                "accepted_at": fields.Datetime.now(),
                "accepted_by_id": response_user.id,
                "acceptance_source": source,
            })
            offer.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_offer_accepted",
                next_action="Request applicant employment requirements",
                next_action_date=fields.Date.add(fields.Date.context_today(offer), days=2),
                message="Your offer has been accepted. SEDAR HR will request your employment requirements next.",
            )
        return True

    def _ensure_offer_decision_authority(self):
        if not self.env.user.has_group("hr_recruitment.group_hr_recruitment_manager"):
            raise UserError("Only an HR Recruitment Manager may issue or confirm hiring offers.")
        return True

    def action_decline(self):
        self._ensure_offer_decision_authority()
        return self._action_decline_with_audit()

    def action_decline_from_portal(self, response_user):
        if not response_user or response_user._is_public():
            raise UserError("A signed-in applicant portal user is required to decline an offer.")
        return self._action_decline_with_audit()

    def _action_decline_with_audit(self):
        for offer in self:
            if offer.state != "issued":
                raise UserError("Only an issued offer can be declined.")
            offer.write({"state": "declined", "declined_at": fields.Datetime.now()})
            offer.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_rejected",
                next_action=False,
                message="The employment offer was declined and the application has been closed.",
            )
        return True

    def action_withdraw(self):
        self._ensure_offer_decision_authority()
        for offer in self:
            if offer.state not in ("draft", "issued"):
                raise UserError("Only draft or issued offers can be withdrawn.")
            offer.write({"state": "withdrawn"})
            offer.applicant_id.write({
                "sedar_next_action": "Review hiring decision",
                "sedar_action_required": False,
                "sedar_action_instructions": False,
            })
        return True

    def action_expire(self):
        self._ensure_offer_decision_authority()
        for offer in self:
            if offer.state != "issued":
                raise UserError("Only issued offers can expire.")
            offer.write({"state": "expired"})
            offer.applicant_id._move_to_sedar_stage(
                "sedar_recruitment_operations.stage_rejected",
                next_action=False,
                message="The employment offer expired and the application has been closed.",
            )
        return True

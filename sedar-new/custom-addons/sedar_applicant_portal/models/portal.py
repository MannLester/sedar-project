import secrets

from odoo import api, fields, models


PUBLIC_STATUSES = [
    ("received", "Application Received"),
    ("under_review", "Under Review"),
    ("shortlisted", "Shortlisted"),
    ("interview", "Interview Stage"),
    ("requirements", "Additional Requirements Needed"),
    ("final_review", "Final Review"),
    ("offer", "Offer Stage"),
    ("successful", "Application Successful"),
    ("closed", "Application Closed"),
]


class SedarRecruitmentStage(models.Model):
    _inherit = "hr.recruitment.stage"

    sedar_public_status = fields.Selection(PUBLIC_STATUSES, string="Applicant Status")
    sedar_public_title = fields.Char(string="Applicant Status Title")
    sedar_public_message = fields.Text(string="Applicant Status Message")
    sedar_public_action_required = fields.Boolean(string="Applicant Action Required")


class SedarApplicantPortal(models.Model):
    _inherit = "hr.applicant"

    sedar_portal_partner_id = fields.Many2one("res.partner", string="Verified Portal Owner", readonly=True, copy=False, index=True)
    sedar_claim_token = fields.Char(string="Portal Claim Token", readonly=True, copy=False, index=True)
    sedar_claim_expires_at = fields.Datetime(string="Claim Expires At", readonly=True, copy=False)
    sedar_portal_claimed_at = fields.Datetime(string="Portal Claimed At", readonly=True, copy=False)
    sedar_claim_url = fields.Char(compute="_compute_claim_url", string="Portal Activation URL")
    sedar_public_status = fields.Selection(PUBLIC_STATUSES, string="Applicant Status", default="received", required=True, tracking=True)
    sedar_public_status_label = fields.Char(compute="_compute_public_status_label")
    sedar_public_message = fields.Text(string="Applicant Message", tracking=True)
    sedar_status_updated_at = fields.Datetime(string="Status Updated At", readonly=True, copy=False)
    sedar_action_required = fields.Boolean(string="Applicant Action Required", tracking=True)
    sedar_action_instructions = fields.Text(string="Applicant Instructions")
    sedar_portal_event_ids = fields.One2many("sedar.applicant.portal.event", "applicant_id", string="Applicant Timeline")

    _claim_token_unique = models.Constraint("UNIQUE(sedar_claim_token)", "Portal claim token must be unique.")

    @api.depends("sedar_public_status")
    def _compute_public_status_label(self):
        labels = dict(PUBLIC_STATUSES)
        for applicant in self:
            applicant.sedar_public_status_label = labels.get(applicant.sedar_public_status, applicant.sedar_public_status)

    @api.depends("sedar_claim_token")
    def _compute_claim_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for applicant in self:
            applicant.sedar_claim_url = "%s/careers/application/activate/%s" % (base_url.rstrip("/"), applicant.sedar_claim_token) if applicant.sedar_claim_token else False

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("sedar_public_status", "received")
            vals.setdefault("sedar_status_updated_at", now)
            vals.setdefault("sedar_claim_token", secrets.token_urlsafe(32))
            vals.setdefault("sedar_claim_expires_at", fields.Datetime.add(now, days=2))
        applicants = super().create(vals_list)
        for applicant in applicants:
            applicant._create_portal_event("received", "Application Received", "Your application was received by SEDAR.")
        return applicants

    def write(self, vals):
        status_changed = "sedar_public_status" in vals
        result = super().write(vals)
        if status_changed:
            now = fields.Datetime.now()
            self.write({"sedar_status_updated_at": now})
            for applicant in self:
                title = dict(PUBLIC_STATUSES).get(applicant.sedar_public_status, applicant.sedar_public_status)
                applicant._create_portal_event(applicant.sedar_public_status, title, applicant.sedar_public_message or title)
        return result

    def _create_portal_event(self, event_type, title, message):
        self.ensure_one()
        self.env["sedar.applicant.portal.event"].sudo().create({
            "applicant_id": self.id,
            "event_type": event_type,
            "title": title,
            "message": message,
            "occurred_at": fields.Datetime.now(),
            "visible": True,
        })

    def action_regenerate_claim_token(self):
        self.write({
            "sedar_claim_token": secrets.token_urlsafe(32),
            "sedar_claim_expires_at": fields.Datetime.add(fields.Datetime.now(), days=2),
        })
        return True

    def action_revoke_portal_access(self):
        for applicant in self:
            if applicant.sedar_portal_partner_id:
                users = applicant.sedar_portal_partner_id.user_ids.filtered(lambda user: user.share)
                users.write({"active": False})
            applicant.write({"sedar_portal_partner_id": False, "sedar_portal_claimed_at": False})
        return True


class SedarApplicantPortalEvent(models.Model):
    _name = "sedar.applicant.portal.event"
    _description = "Applicant Visible Timeline Event"
    _order = "occurred_at desc, id desc"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    event_type = fields.Selection(PUBLIC_STATUSES, required=True)
    title = fields.Char(required=True)
    message = fields.Text()
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now)
    visible = fields.Boolean(default=True)

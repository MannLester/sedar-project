import secrets

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarApplicant(models.Model):
    _inherit = "hr.applicant"

    sedar_vacancy_id = fields.Many2one("sedar.job.vacancy", string="SEDAR Vacancy", ondelete="restrict", index=True)
    sedar_reference = fields.Char(string="Application Reference", readonly=True, copy=False, index=True)
    sedar_intake_state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("under_review", "Under HR Review"),
    ], default="draft", required=True, tracking=True)
    sedar_document_type_id = fields.Many2one("sedar.document.type", string="Source Document", readonly=True, ondelete="restrict")
    sedar_document_revision = fields.Char(string="Source Revision", readonly=True)
    sedar_consent = fields.Boolean(string="Privacy Consent", readonly=True)
    sedar_consent_at = fields.Datetime(string="Consent Given At", readonly=True)
    sedar_tracking_token = fields.Char(readonly=True, copy=False, index=True)
    sedar_duplicate_warning = fields.Boolean(string="Possible Duplicate", readonly=True)
    sedar_profile_id = fields.Many2one("sedar.applicant.profile", string="ADM-3 Profile", readonly=True, ondelete="set null")
    sedar_education_ids = fields.One2many("sedar.applicant.education", "applicant_id", string="Education")
    sedar_employment_ids = fields.One2many("sedar.applicant.employment", "applicant_id", string="Employment History")
    sedar_document_ids = fields.One2many("sedar.applicant.document", "applicant_id", string="Submitted Documents")

    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        for applicant in applicants:
            if not applicant.sedar_reference:
                applicant.sedar_reference = self.env["ir.sequence"].next_by_code("sedar.applicant") or "APP-NEW"
            if not applicant.sedar_tracking_token:
                applicant.sedar_tracking_token = secrets.token_urlsafe(32)
        return applicants

    def action_mark_under_review(self):
        self.write({"sedar_intake_state": "under_review"})


class SedarApplicantProfile(models.Model):
    _name = "sedar.applicant.profile"
    _description = "SEDAR ADM-3 Applicant Profile"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    family_name = fields.Char(required=True)
    given_name = fields.Char(required=True)
    middle_name = fields.Char()
    fathers_name = fields.Char(string="Father's Name")
    date_of_birth = fields.Date()
    place_of_birth = fields.Char()
    age = fields.Integer()
    height = fields.Float()
    weight = fields.Float()
    civil_status = fields.Selection([
        ("single", "Single"), ("married", "Married"), ("widowed", "Widowed"),
        ("separated", "Legally Separated"),
    ])
    contact_information = fields.Text()
    identity_documents = fields.Text(string="SIRB / Driver's License Details")
    skills = fields.Text()
    training_entries = fields.Text(string="Trainings and Seminars")
    medical_entries = fields.Text(string="Medical Examination Details")
    emergency_contact = fields.Text()
    certification_date = fields.Date()
    electronic_signature = fields.Char(string="Electronic Signature")
    signature_date = fields.Date()

    _applicant_unique = models.Constraint("UNIQUE(applicant_id)", "Each application can have only one ADM-3 profile.")


class SedarApplicantEducation(models.Model):
    _name = "sedar.applicant.education"
    _description = "SEDAR Applicant Education and Skills Entry"
    _order = "date_from, id"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    school_name = fields.Char(required=True)
    course_name = fields.Char()
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    english_knowledge = fields.Char()


class SedarApplicantEmployment(models.Model):
    _name = "sedar.applicant.employment"
    _description = "SEDAR Applicant Employment History"
    _order = "date_from desc, id desc"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    company_address = fields.Text(string="Company / Address", required=True)
    position = fields.Char(required=True)
    reason_for_leaving = fields.Text()


class SedarApplicantDocument(models.Model):
    _name = "sedar.applicant.document"
    _description = "SEDAR Applicant Submitted Document"
    _order = "create_date desc, id desc"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="cascade")
    category = fields.Selection([
        ("resume", "Resume / CV"), ("photo", "Applicant Photo"),
        ("cover_letter", "Cover Letter"), ("certificate", "Certificate / License"),
        ("identity", "SIRB / Driver's License"), ("other", "Other Supporting Document"),
    ], required=True)
    filename = fields.Char(related="attachment_id.name", readonly=True)
    mimetype = fields.Char(related="attachment_id.mimetype", readonly=True)
    verification_state = fields.Selection([
        ("pending", "Pending Review"), ("verified", "Verified"),
        ("rejected", "Rejected"),
    ], default="pending", required=True)
    verification_notes = fields.Text()

    @api.constrains("attachment_id")
    def _check_attachment_owner(self):
        for document in self:
            if document.attachment_id.res_model != "hr.applicant" or document.attachment_id.res_id != document.applicant_id.id:
                raise ValidationError("The submitted document must be attached to its application.")

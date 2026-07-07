from odoo import fields, models


class SedarApplicantProfile(models.Model):
    _name = 'sedar.applicant.profile'
    _description = 'SEDAR Applicant Profile'
    _order = 'create_date desc, id desc'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade')

    family_name = fields.Char(required=True)
    given_name = fields.Char(required=True)
    middle_name = fields.Char(required=True)
    father_name = fields.Char(required=True)
    date_of_birth = fields.Date(required=True)
    place_of_birth = fields.Char(required=True)
    religion = fields.Char(required=True)
    mother_name = fields.Char(required=True)
    age = fields.Integer(required=True)
    height = fields.Float(required=True)
    weight = fields.Float(required=True)
    next_of_kin = fields.Char(required=True)
    sss_no = fields.Char(string='SSS #', required=True)
    tin_no = fields.Char(string='TIN #', required=True)
    philhealth_no = fields.Char(string='PHILHEALTH #', required=True)
    pagibig_no = fields.Char(string='PAGIBIG #', required=True)
    civil_status = fields.Selection(
        [
            ('single', 'Single'),
            ('married', 'Married'),
            ('widowed', 'Widowed'),
            ('separated', 'Separated'),
        ],
        required=True,
    )

    email = fields.Char(required=True)
    telephone = fields.Char(required=True)
    mobile = fields.Char(required=True)
    city_address = fields.Text(required=True)
    provincial_address = fields.Text(required=True)

    sirb_number = fields.Char(string='SIRB Number', required=True)
    sirb_date_issued = fields.Date(string='SIRB Date Issued', required=True)
    sirb_expiry_date = fields.Date(string='SIRB Expiry Date', required=True)
    sirb_attachment_id = fields.Many2one('ir.attachment', string='SIRB Attachment', readonly=True)
    drivers_license_number = fields.Char(string="Driver's License Number", required=True)
    drivers_license_date_issued = fields.Date(string="Driver's License Date Issued", required=True)
    drivers_license_expiry_date = fields.Date(string="Driver's License Expiry Date", required=True)
    drivers_license_attachment_id = fields.Many2one('ir.attachment', string="Driver's License Attachment", readonly=True)
    resume_attachment_id = fields.Many2one('ir.attachment', string='Resume Attachment', readonly=True)

    college_school = fields.Char(string='College/School Last Attended', required=True)
    course = fields.Char(required=True)
    education_from = fields.Date(required=True)
    education_to = fields.Date(required=True)
    english_knowledge = fields.Char(required=True)

    training_ids = fields.One2many('sedar.applicant.training', 'profile_id', string='Trainings and Seminars')

    medical_date_exam = fields.Date(string='Date of Exam', required=True)
    medical_clinic = fields.Char(required=True)
    medical_basic_result = fields.Char(string='Basic Result', required=True)
    medical_drug_alcohol_result = fields.Char(string='Drug and Alcohol Result', required=True)
    medical_ecg_result = fields.Char(string='ECG Result', required=True)

    employment_ids = fields.One2many('sedar.applicant.employment', 'profile_id', string='Employment History')

    legal_case = fields.Selection([('yes', 'Yes'), ('no', 'No')], required=True)
    legal_case_details = fields.Text()
    union_member = fields.Selection([('yes', 'Yes'), ('no', 'No')], required=True)
    union_member_details = fields.Text()
    disability_benefits = fields.Selection([('yes', 'Yes'), ('no', 'No')], required=True)
    disability_benefits_details = fields.Text()

    beneficiary_name = fields.Char(required=True)
    beneficiary_date_of_birth = fields.Date(required=True)
    beneficiary_contact_number = fields.Char(required=True)
    beneficiary_address = fields.Text(required=True)
    dependent_count = fields.Integer(required=True)
    dependent_ids = fields.One2many('sedar.applicant.dependent', 'profile_id', string='Dependents')

    notify_name = fields.Char(required=True)
    notify_relationship = fields.Char(required=True)
    notify_contact_number = fields.Char(required=True)
    notify_address = fields.Text(required=True)

    certification_agreed = fields.Boolean(required=True)
    certification_name = fields.Char(required=True)
    certification_date = fields.Date(required=True)
    signature_placeholder = fields.Char(default='Signature placeholder', readonly=True)


class SedarApplicantTraining(models.Model):
    _name = 'sedar.applicant.training'
    _description = 'SEDAR Applicant Training'

    profile_id = fields.Many2one('sedar.applicant.profile', required=True, ondelete='cascade')
    seminar_name = fields.Char(required=True)
    cert_no = fields.Char(string='Cert. No.', required=True)
    inclusive_dates = fields.Char(required=True)
    venue = fields.Char(required=True)
    seminar_provider = fields.Char(required=True)


class SedarApplicantEmployment(models.Model):
    _name = 'sedar.applicant.employment'
    _description = 'SEDAR Applicant Employment History'

    profile_id = fields.Many2one('sedar.applicant.profile', required=True, ondelete='cascade')
    inclusive_dates = fields.Char(required=True)
    company_address = fields.Text(string='Name of Company/Address', required=True)
    position = fields.Char(required=True)
    reason_leaving = fields.Text(string='Reason for Leaving', required=True)


class SedarApplicantDependent(models.Model):
    _name = 'sedar.applicant.dependent'
    _description = 'SEDAR Applicant Dependent'

    profile_id = fields.Many2one('sedar.applicant.profile', required=True, ondelete='cascade')
    name = fields.Char(required=True)
    relation = fields.Char(required=True)
    date_of_birth = fields.Date(required=True)
    remarks = fields.Text(required=True)

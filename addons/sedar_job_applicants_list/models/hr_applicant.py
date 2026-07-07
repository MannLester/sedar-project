from odoo import _, api, fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sedar_portal_profile_id = fields.Many2one(
        'sedar.applicant.profile',
        string='Portal Submission',
        compute='_compute_sedar_portal_profile',
        store=True,
        index=True,
    )
    sedar_portal_family_name = fields.Char(related='sedar_portal_profile_id.family_name')
    sedar_portal_given_name = fields.Char(related='sedar_portal_profile_id.given_name')
    sedar_portal_middle_name = fields.Char(related='sedar_portal_profile_id.middle_name')
    sedar_portal_father_name = fields.Char(related='sedar_portal_profile_id.father_name')
    sedar_portal_date_of_birth = fields.Date(related='sedar_portal_profile_id.date_of_birth')
    sedar_portal_place_of_birth = fields.Char(related='sedar_portal_profile_id.place_of_birth')
    sedar_portal_religion = fields.Char(related='sedar_portal_profile_id.religion')
    sedar_portal_mother_name = fields.Char(related='sedar_portal_profile_id.mother_name')
    sedar_portal_age = fields.Integer(related='sedar_portal_profile_id.age')
    sedar_portal_height = fields.Float(related='sedar_portal_profile_id.height')
    sedar_portal_weight = fields.Float(related='sedar_portal_profile_id.weight')
    sedar_portal_next_of_kin = fields.Char(related='sedar_portal_profile_id.next_of_kin')
    sedar_portal_sss_no = fields.Char(related='sedar_portal_profile_id.sss_no')
    sedar_portal_tin_no = fields.Char(related='sedar_portal_profile_id.tin_no')
    sedar_portal_philhealth_no = fields.Char(related='sedar_portal_profile_id.philhealth_no')
    sedar_portal_pagibig_no = fields.Char(related='sedar_portal_profile_id.pagibig_no')
    sedar_portal_civil_status = fields.Selection(related='sedar_portal_profile_id.civil_status')

    sedar_portal_email = fields.Char(string='Portal Email', related='sedar_portal_profile_id.email')
    sedar_portal_telephone = fields.Char(related='sedar_portal_profile_id.telephone')
    sedar_portal_mobile = fields.Char(string='Portal Mobile', related='sedar_portal_profile_id.mobile')
    sedar_portal_city_address = fields.Text(related='sedar_portal_profile_id.city_address')
    sedar_portal_provincial_address = fields.Text(related='sedar_portal_profile_id.provincial_address')

    sedar_portal_sirb_number = fields.Char(related='sedar_portal_profile_id.sirb_number')
    sedar_portal_sirb_date_issued = fields.Date(related='sedar_portal_profile_id.sirb_date_issued')
    sedar_portal_sirb_expiry_date = fields.Date(related='sedar_portal_profile_id.sirb_expiry_date')
    sedar_portal_sirb_attachment_id = fields.Many2one(related='sedar_portal_profile_id.sirb_attachment_id')
    sedar_portal_drivers_license_number = fields.Char(related='sedar_portal_profile_id.drivers_license_number')
    sedar_portal_drivers_license_date_issued = fields.Date(related='sedar_portal_profile_id.drivers_license_date_issued')
    sedar_portal_drivers_license_expiry_date = fields.Date(related='sedar_portal_profile_id.drivers_license_expiry_date')
    sedar_portal_drivers_license_attachment_id = fields.Many2one(related='sedar_portal_profile_id.drivers_license_attachment_id')
    sedar_portal_resume_attachment_id = fields.Many2one(related='sedar_portal_profile_id.resume_attachment_id')

    sedar_portal_college_school = fields.Char(related='sedar_portal_profile_id.college_school')
    sedar_portal_course = fields.Char(related='sedar_portal_profile_id.course')
    sedar_portal_education_from = fields.Date(related='sedar_portal_profile_id.education_from')
    sedar_portal_education_to = fields.Date(related='sedar_portal_profile_id.education_to')
    sedar_portal_english_knowledge = fields.Char(related='sedar_portal_profile_id.english_knowledge')
    sedar_portal_training_ids = fields.One2many(related='sedar_portal_profile_id.training_ids')

    sedar_portal_medical_date_exam = fields.Date(related='sedar_portal_profile_id.medical_date_exam')
    sedar_portal_medical_clinic = fields.Char(related='sedar_portal_profile_id.medical_clinic')
    sedar_portal_medical_basic_result = fields.Char(related='sedar_portal_profile_id.medical_basic_result')
    sedar_portal_medical_drug_alcohol_result = fields.Char(related='sedar_portal_profile_id.medical_drug_alcohol_result')
    sedar_portal_medical_ecg_result = fields.Char(related='sedar_portal_profile_id.medical_ecg_result')
    sedar_portal_employment_ids = fields.One2many(related='sedar_portal_profile_id.employment_ids')

    sedar_portal_legal_case = fields.Selection(related='sedar_portal_profile_id.legal_case')
    sedar_portal_legal_case_details = fields.Text(related='sedar_portal_profile_id.legal_case_details')
    sedar_portal_union_member = fields.Selection(related='sedar_portal_profile_id.union_member')
    sedar_portal_union_member_details = fields.Text(related='sedar_portal_profile_id.union_member_details')
    sedar_portal_disability_benefits = fields.Selection(related='sedar_portal_profile_id.disability_benefits')
    sedar_portal_disability_benefits_details = fields.Text(related='sedar_portal_profile_id.disability_benefits_details')

    sedar_portal_beneficiary_name = fields.Char(related='sedar_portal_profile_id.beneficiary_name')
    sedar_portal_beneficiary_date_of_birth = fields.Date(related='sedar_portal_profile_id.beneficiary_date_of_birth')
    sedar_portal_beneficiary_contact_number = fields.Char(related='sedar_portal_profile_id.beneficiary_contact_number')
    sedar_portal_beneficiary_address = fields.Text(related='sedar_portal_profile_id.beneficiary_address')
    sedar_portal_dependent_count = fields.Integer(related='sedar_portal_profile_id.dependent_count')
    sedar_portal_dependent_ids = fields.One2many(related='sedar_portal_profile_id.dependent_ids')
    sedar_portal_notify_name = fields.Char(related='sedar_portal_profile_id.notify_name')
    sedar_portal_notify_relationship = fields.Char(related='sedar_portal_profile_id.notify_relationship')
    sedar_portal_notify_contact_number = fields.Char(related='sedar_portal_profile_id.notify_contact_number')
    sedar_portal_notify_address = fields.Text(related='sedar_portal_profile_id.notify_address')

    sedar_portal_certification_agreed = fields.Boolean(related='sedar_portal_profile_id.certification_agreed')
    sedar_portal_certification_name = fields.Char(related='sedar_portal_profile_id.certification_name')
    sedar_portal_certification_date = fields.Date(related='sedar_portal_profile_id.certification_date')
    sedar_portal_signature_placeholder = fields.Char(related='sedar_portal_profile_id.signature_placeholder')

    @api.depends('sedar_applicant_profile_ids')
    def _compute_sedar_portal_profile(self):
        for applicant in self:
            applicant.sedar_portal_profile_id = applicant.sedar_applicant_profile_ids[:1]

    def action_sedar_email_placeholder(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email'),
                'message': _('Email action placeholder for %s.') % self.display_name,
                'type': 'info',
                'sticky': False,
            },
        }

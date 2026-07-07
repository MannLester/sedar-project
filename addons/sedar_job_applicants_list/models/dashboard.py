from odoo import fields, models


class SedarDashboard(models.Model):
    _inherit = 'sedar.dashboard'

    sedar_job_applicant_ids = fields.Many2many(
        'hr.applicant',
        compute='_compute_sedar_job_applicants',
        string='Job Applicants',
    )
    sedar_job_applicant_count = fields.Integer(compute='_compute_sedar_job_applicants')

    def _compute_sedar_job_applicants(self):
        applicants = self.env['hr.applicant'].search(
            [('sedar_hiring_state', 'in', ['application', 'for_interview', 'final_assessment', 'contract_signing'])],
            order='create_date desc, id desc',
        )
        for dashboard in self:
            dashboard.sedar_job_applicant_ids = applicants
            dashboard.sedar_job_applicant_count = len(applicants)

    def action_sedar_open_job_applicants(self):
        return self.env.ref('sedar_job_applicants_list.action_sedar_dashboard_job_applicants').read()[0]

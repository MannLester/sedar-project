from odoo import api, fields, models


class SedarJobHiringOverview(models.Model):
    _name = 'sedar.job.hiring.overview'
    _description = 'Job Hiring Overview Card'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(default='fa-users')
    description = fields.Text()
    action_xmlid = fields.Char(required=True)
    color = fields.Integer(default=0)
    record_count = fields.Integer(compute='_compute_record_count')

    def _compute_record_count(self):
        count_map = {
            'sedar_recruitment_link.action_sedar_job_dispatch': self.env['sedar.job.dispatch'].search_count([]),
            'sedar_recruitment_link.action_sedar_job_applications': self.env['hr.applicant'].search_count([('sedar_hiring_state', '=', 'application')]),
            'sedar_recruitment_link.action_sedar_pending_interviews': self.env['hr.applicant'].search_count([('sedar_hiring_state', '=', 'for_interview')]),
            'sedar_recruitment_link.action_sedar_final_assessment': self.env['hr.applicant'].search_count([('sedar_hiring_state', '=', 'final_assessment')]),
            'sedar_recruitment_link.action_sedar_contract_signing': self.env['hr.applicant'].search_count([('sedar_hiring_state', '=', 'contract_signing')]),
        }
        for card in self:
            card.record_count = count_map.get(card.action_xmlid, 0)

    def action_open_target(self):
        self.ensure_one()
        action = self.env.ref(self.action_xmlid).sudo().read()[0]
        return action

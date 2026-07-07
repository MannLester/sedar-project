from odoo import fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sedar_applicant_profile_ids = fields.One2many(
        'sedar.applicant.profile',
        'applicant_id',
        string='Applicant Portal Profile',
    )

    def action_sedar_view_applicant_profile(self):
        self.ensure_one()
        return {
            'name': 'Applicant Portal Profile',
            'type': 'ir.actions.act_window',
            'res_model': 'sedar.applicant.profile',
            'view_mode': 'form',
            'target': 'current',
            'domain': [('applicant_id', '=', self.id)],
            'context': {'default_applicant_id': self.id},
        }

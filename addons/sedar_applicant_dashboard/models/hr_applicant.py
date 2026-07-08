import uuid

from odoo import api, fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sedar_dashboard_token = fields.Char(
        string='Applicant Dashboard Token',
        copy=False,
        index=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            'sedar_dashboard_token_unique',
            'unique(sedar_dashboard_token)',
            'Applicant dashboard tokens must be unique.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('sedar_dashboard_token', self._sedar_generate_dashboard_token())
        return super().create(vals_list)

    @api.model
    def _sedar_generate_dashboard_token(self):
        token = uuid.uuid4().hex
        while self.sudo().search_count([('sedar_dashboard_token', '=', token)]):
            token = uuid.uuid4().hex
        return token

    def _sedar_ensure_dashboard_token(self):
        for applicant in self.sudo():
            if not applicant.sedar_dashboard_token:
                applicant.sedar_dashboard_token = self._sedar_generate_dashboard_token()
        return self

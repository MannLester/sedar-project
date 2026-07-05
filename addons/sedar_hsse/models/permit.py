from odoo import fields, models


class SedarHssePermit(models.Model):
    _name = 'sedar.hsse.permit'
    _description = 'HSSE Permit'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    name = fields.Char(required=True)
    permit_type = fields.Char(required=True)
    issuing_authority = fields.Selection(
        [('marina', 'MARINA'), ('pcg', 'PCG'), ('ppa', 'PPA'), ('lgu', 'LGU'), ('other', 'Other')],
        string='Issuing Authority',
        default='marina',
        required=True,
    )
    issue_date = fields.Date()
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')

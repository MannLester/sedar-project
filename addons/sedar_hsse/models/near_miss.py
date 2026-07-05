from odoo import fields, models


class SedarHsseNearMiss(models.Model):
    _name = 'sedar.hsse.near.miss'
    _description = 'HSSE Near-Miss Report'
    _order = 'date desc'

    name = fields.Char(default='Near Miss', required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    reporter_id = fields.Many2one('res.users', string='Reporter', default=lambda self: self.env.user)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    description = fields.Text(required=True)
    risk_category = fields.Selection(
        [
            ('personnel', 'Personnel'),
            ('equipment', 'Equipment'),
            ('environment', 'Environment'),
            ('navigation', 'Navigation'),
            ('other', 'Other'),
        ],
        default='other',
        required=True,
    )

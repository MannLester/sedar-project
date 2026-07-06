from odoo import fields, models


class SedarCrewMedical(models.Model):
    _name = 'sedar.crew.medical'
    _description = 'Crew Medical Certificate'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    crew_id = fields.Many2one('sedar.crew.member', string='Crew Member', required=True)
    exam_date = fields.Date()
    fit_for_duty = fields.Boolean(default=True)
    clinic = fields.Char()

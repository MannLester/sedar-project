from odoo import fields, models


class SedarCrewCertification(models.Model):
    _name = 'sedar.crew.certification'
    _description = 'Crew Certification'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    crew_id = fields.Many2one('sedar.crew.member', string='Crew Member', required=True)
    cert_type = fields.Char(string='STCW Certificate Type', required=True)
    issue_date = fields.Date()
    certificate_no = fields.Char()

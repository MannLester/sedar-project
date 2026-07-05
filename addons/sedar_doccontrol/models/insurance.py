from odoo import fields, models


class SedarDocInsurance(models.Model):
    _name = 'sedar.doc.insurance'
    _description = 'Insurance Policy'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    policy_no = fields.Char(required=True)
    name = fields.Char(related='policy_no', store=True, readonly=True)
    insurer = fields.Char(required=True)
    coverage_type = fields.Char(required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    attachment = fields.Binary(string='File Attachment')
    attachment_filename = fields.Char()

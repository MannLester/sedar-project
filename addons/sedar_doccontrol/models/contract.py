from odoo import fields, models


class SedarDocContract(models.Model):
    _name = 'sedar.doc.contract'
    _description = 'Controlled Contract'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    name = fields.Char(required=True)
    partner_id = fields.Many2one('res.partner', string='Counterparty', required=True)
    contract_type = fields.Char(required=True)
    effective_date = fields.Date()
    attachment = fields.Binary(string='File Attachment')
    attachment_filename = fields.Char()

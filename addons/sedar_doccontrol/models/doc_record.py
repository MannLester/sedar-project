from odoo import fields, models


class SedarDocRecord(models.Model):
    _name = 'sedar.doc.record'
    _description = 'Controlled Document Record'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    name = fields.Char(required=True)
    category = fields.Selection(
        [
            ('permit', 'Permit'),
            ('board_resolution', 'Board Resolution'),
            ('iso', 'ISO Document'),
            ('policy', 'Policy'),
            ('other', 'Other'),
        ],
        default='permit',
        required=True,
    )
    reference_no = fields.Char()
    issuing_body = fields.Char()
    issue_date = fields.Date()
    attachment = fields.Binary(string='File Attachment')
    attachment_filename = fields.Char()

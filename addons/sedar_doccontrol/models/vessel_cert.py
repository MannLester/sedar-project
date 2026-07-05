from odoo import api, fields, models


class SedarDocVesselCert(models.Model):
    _name = 'sedar.doc.vessel.cert'
    _description = 'Vessel Certificate'
    _inherit = ['sedar.expiry.mixin']
    _order = 'expiry_date'

    name = fields.Char(compute='_compute_name', store=True)
    cert_type = fields.Char(required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True)
    issuing_body = fields.Char()
    issue_date = fields.Date()

    @api.depends('vessel_id', 'cert_type')
    def _compute_name(self):
        for rec in self:
            vessel = rec.vessel_id.name or 'Vessel'
            cert_type = rec.cert_type or 'Certificate'
            rec.name = '%s - %s' % (vessel, cert_type)

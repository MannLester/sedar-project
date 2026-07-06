from odoo import fields, models


class SedarHsseInspection(models.Model):
    _name = 'sedar.hsse.inspection'
    _description = 'HSSE Inspection / Audit'
    _order = 'date desc'

    name = fields.Char(default='Inspection', required=True)
    inspection_type = fields.Selection(
        [('vessel', 'Vessel'), ('port', 'Port'), ('office', 'Office'), ('audit', 'Audit')],
        default='vessel',
        required=True,
    )
    auditor_id = fields.Many2one('res.users', string='Auditor', default=lambda self: self.env.user)
    date = fields.Date(required=True, default=fields.Date.context_today)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    findings = fields.Text()
    line_ids = fields.One2many('sedar.hsse.inspection.line', 'inspection_id', string='Checklist')


class SedarHsseInspectionLine(models.Model):
    _name = 'sedar.hsse.inspection.line'
    _description = 'HSSE Inspection Checklist Line'

    inspection_id = fields.Many2one('sedar.hsse.inspection', required=True, ondelete='cascade')
    item = fields.Char(required=True)
    result = fields.Selection([('pass', 'Pass'), ('fail', 'Fail')], default='pass', required=True)
    remarks = fields.Char()

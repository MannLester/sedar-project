from odoo import fields, models


class SedarHsseIncident(models.Model):
    _name = 'sedar.hsse.incident'
    _description = 'HSSE Incident'
    _order = 'date desc'

    name = fields.Char(default='Incident', required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    location = fields.Char()
    severity = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='low',
        required=True,
    )
    description = fields.Text(required=True)
    corrective_action = fields.Text()
    state = fields.Selection(
        [('open', 'Open'), ('investigating', 'Investigating'), ('closed', 'Closed')],
        default='open',
        string='Status',
        required=True,
    )

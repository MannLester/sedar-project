from odoo import api, fields, models


class SedarHsseRiskAssessment(models.Model):
    _name = 'sedar.hsse.risk.assessment'
    _description = 'HSSE Risk Assessment'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    activity = fields.Char(required=True)
    hazard = fields.Char(required=True)
    likelihood = fields.Selection(
        [('1', '1 - Rare'), ('2', '2 - Unlikely'), ('3', '3 - Possible'), ('4', '4 - Likely'), ('5', '5 - Almost Certain')],
        default='1',
        required=True,
    )
    severity = fields.Selection(
        [('1', '1 - Minor'), ('2', '2 - Moderate'), ('3', '3 - Serious'), ('4', '4 - Major'), ('5', '5 - Catastrophic')],
        default='1',
        required=True,
    )
    risk_score = fields.Integer(compute='_compute_risk_score', store=True)
    mitigation = fields.Text()

    @api.depends('activity', 'hazard')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s - %s' % (rec.activity or 'Activity', rec.hazard or 'Hazard')

    @api.depends('likelihood', 'severity')
    def _compute_risk_score(self):
        for rec in self:
            rec.risk_score = int(rec.likelihood or 0) * int(rec.severity or 0)

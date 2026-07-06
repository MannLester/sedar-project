from odoo import api, fields, models


class SedarFuelLog(models.Model):
    _name = 'sedar.fuel.log'
    _description = 'Fuel Monitoring'
    _order = 'date desc'

    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    liters = fields.Float(required=True)
    cost = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    cost_per_liter = fields.Monetary(
        compute='_compute_cost_per_liter',
        currency_field='currency_id',
        store=True,
    )
    notes = fields.Text()

    @api.depends('liters', 'cost')
    def _compute_cost_per_liter(self):
        for rec in self:
            rec.cost_per_liter = rec.cost / rec.liters if rec.liters else 0.0

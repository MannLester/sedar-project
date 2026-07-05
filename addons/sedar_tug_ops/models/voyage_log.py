from odoo import fields, models


class SedarVoyageLog(models.Model):
    _name = 'sedar.voyage.log'
    _description = 'Voyage Log'
    _order = 'departure_time desc'

    job_order_id = fields.Many2one('sedar.job.order', string='Job Order', required=True)
    vessel_id = fields.Many2one(related='job_order_id.vessel_id', store=True, readonly=True)
    departure_time = fields.Datetime(default=fields.Datetime.now)
    arrival_time = fields.Datetime()
    distance_nm = fields.Float(string='Distance (NM)')
    weather_notes = fields.Text()

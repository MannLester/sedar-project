from odoo import api, fields, models


class SedarVesselTrackingLog(models.Model):
    _name = 'sedar.vessel.tracking.log'
    _description = 'Vessel GPS/AIS Tracking Log'
    _order = 'timestamp desc'

    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True, ondelete='cascade')
    timestamp = fields.Datetime(required=True, default=fields.Datetime.now)
    latitude = fields.Float(required=True, digits=(10, 6))
    longitude = fields.Float(required=True, digits=(10, 6))
    speed_knots = fields.Float(string='Speed (knots)')
    course_degrees = fields.Float(string='Course')
    source = fields.Selection(
        [('manual', 'Manual'), ('gps', 'GPS'), ('ais', 'AIS')],
        default='manual',
        required=True,
    )
    port_area = fields.Char()
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.vessel_id.write({
                'current_latitude': rec.latitude,
                'current_longitude': rec.longitude,
                'speed_knots': rec.speed_knots,
                'course_degrees': rec.course_degrees,
                'last_position_at': rec.timestamp,
            })
        return records

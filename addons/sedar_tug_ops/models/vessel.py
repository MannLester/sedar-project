from odoo import api, fields, models


class SedarVessel(models.Model):
    _name = 'sedar.vessel'
    _description = 'Tugboat / Barge Vessel'
    _order = 'name'

    name = fields.Char(required=True)
    registry_no = fields.Char(string='IMO/Registry No.')
    vessel_type = fields.Selection(
        [('tug', 'Tug'), ('barge', 'Barge')],
        required=True,
        default='tug',
    )
    capacity = fields.Float(string='Capacity (BHP/DWT)')
    home_port = fields.Char(default='Manila South Harbor')
    status = fields.Selection(
        [('active', 'Active'), ('dry_dock', 'Dry Dock'), ('standby', 'Standby')],
        default='active',
        required=True,
    )
    current_latitude = fields.Float(string='Latitude', digits=(10, 6))
    current_longitude = fields.Float(string='Longitude', digits=(10, 6))
    speed_knots = fields.Float(string='Speed (knots)')
    course_degrees = fields.Float(string='Course')
    last_position_at = fields.Datetime(string='Last GPS/AIS Update')
    tracking_status = fields.Selection(
        [('online', 'Online'), ('stale', 'Stale'), ('offline', 'Offline')],
        compute='_compute_tracking_status',
        string='Tracking Status',
    )
    tracking_log_ids = fields.One2many(
        'sedar.vessel.tracking.log',
        'vessel_id',
        string='Tracking History',
    )

    @api.depends('last_position_at')
    def _compute_tracking_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.last_position_at:
                rec.tracking_status = 'offline'
                continue
            age_hours = (now - rec.last_position_at).total_seconds() / 3600
            rec.tracking_status = 'online' if age_hours <= 6 else 'stale'

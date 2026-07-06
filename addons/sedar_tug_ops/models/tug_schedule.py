from odoo import fields, models


class SedarTugSchedule(models.Model):
    _name = 'sedar.tug.schedule'
    _description = 'Tug Scheduling'
    _order = 'start_datetime'

    name = fields.Char(required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True)
    job_order_id = fields.Many2one('sedar.job.order', string='Job Order')
    start_datetime = fields.Datetime(required=True, default=fields.Datetime.now)
    end_datetime = fields.Datetime()
    port_area = fields.Char(required=True)
    assignment_type = fields.Selection(
        [
            ('towage', 'Towage'),
            ('standby', 'Standby'),
            ('maintenance', 'Maintenance'),
            ('dry_dock', 'Dry Dock'),
        ],
        default='towage',
        required=True,
    )
    state = fields.Selection(
        [
            ('planned', 'Planned'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        default='planned',
        required=True,
    )
    notes = fields.Text()

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

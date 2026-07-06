from odoo import api, fields, models


class SedarJobOrder(models.Model):
    _name = 'sedar.job.order'
    _description = 'Tug Job Order / Dispatch'
    _order = 'requested_date desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True)
    origin_port = fields.Char()
    destination_port = fields.Char()
    requested_date = fields.Datetime(required=True, default=fields.Datetime.now)
    state = fields.Selection(
        [
            ('requested', 'Requested'),
            ('dispatched', 'Dispatched'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('billed', 'Billed'),
        ],
        default='requested',
        string='Status',
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sedar.job.order') or 'New'
        return super().create(vals_list)

    def action_dispatch(self):
        self.write({'state': 'dispatched'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed'})

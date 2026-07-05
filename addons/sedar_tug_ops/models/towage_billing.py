from odoo import api, fields, models


class SedarTowageBilling(models.Model):
    _name = 'sedar.towage.billing'
    _description = 'Towage Billing'
    _order = 'id desc'

    name = fields.Char(default='Towage Bill', required=True)
    job_order_id = fields.Many2one('sedar.job.order', string='Job Order', required=True)
    customer_id = fields.Many2one(related='job_order_id.customer_id', store=True, readonly=True)
    rate_basis = fields.Selection(
        [('hour', 'Per Hour'), ('job', 'Per Job')],
        required=True,
        default='job',
    )
    hours = fields.Float(default=1.0)
    rate = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(compute='_compute_amount', currency_field='currency_id', store=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)

    @api.depends('rate_basis', 'hours', 'rate')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.rate * rec.hours if rec.rate_basis == 'hour' else rec.rate

    def action_create_invoice(self):
        for rec in self:
            if rec.invoice_id:
                continue
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.customer_id.id,
                'invoice_line_ids': [(0, 0, {
                    'name': rec.name or rec.job_order_id.name,
                    'quantity': 1.0,
                    'price_unit': rec.amount,
                })],
            })
            rec.invoice_id = invoice
            rec.job_order_id.state = 'billed'
        return True

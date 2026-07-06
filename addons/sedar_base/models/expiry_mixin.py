from odoo import api, fields, models


class SedarExpiryMixin(models.AbstractModel):
    _name = 'sedar.expiry.mixin'
    _description = 'Shared expiry-date tracking'

    expiry_date = fields.Date(string='Expiry Date')
    expiry_status = fields.Selection(
        [('ok', 'Valid'), ('warning', 'Expiring Soon'), ('expired', 'Expired')],
        string='Status',
        compute='_compute_expiry_status',
        store=True,
    )

    @api.depends('expiry_date')
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.expiry_date:
                rec.expiry_status = 'ok'
            elif rec.expiry_date < today:
                rec.expiry_status = 'expired'
            elif (rec.expiry_date - today).days <= 30:
                rec.expiry_status = 'warning'
            else:
                rec.expiry_status = 'ok'

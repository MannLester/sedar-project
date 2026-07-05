from odoo import fields, models


class SedarDashboard(models.Model):
    _name = 'sedar.dashboard'
    _description = 'Management KPI Dashboard'

    name = fields.Char(default='SEDAR KPI Snapshot')
    active_jobs = fields.Integer(compute='_compute_kpis')
    vessel_utilization = fields.Float(compute='_compute_kpis', string='Vessel Utilization %')
    open_incidents = fields.Integer(compute='_compute_kpis')
    expiring_documents = fields.Integer(compute='_compute_kpis')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    monthly_revenue = fields.Monetary(compute='_compute_kpis', currency_field='currency_id')

    def _compute_kpis(self):
        job_order = self.env['sedar.job.order']
        vessel = self.env['sedar.vessel']
        incident = self.env['sedar.hsse.incident']
        invoice = self.env['account.move']
        expiry_models = [
            'sedar.hsse.permit',
            'sedar.crew.certification',
            'sedar.crew.medical',
            'sedar.doc.contract',
            'sedar.doc.vessel.cert',
            'sedar.doc.insurance',
            'sedar.doc.record',
        ]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for rec in self:
            total_vessels = vessel.search_count([])
            active_vessels = vessel.search_count([('status', '=', 'active')])
            rec.active_jobs = job_order.search_count([('state', 'not in', ['completed', 'billed'])])
            rec.vessel_utilization = (active_vessels / total_vessels * 100) if total_vessels else 0.0
            rec.open_incidents = incident.search_count([('state', '!=', 'closed')])
            rec.expiring_documents = sum(
                self.env[model].search_count([('expiry_status', 'in', ['warning', 'expired'])])
                for model in expiry_models
            )
            invoices = invoice.search([
                ('move_type', '=', 'out_invoice'),
                ('invoice_date', '>=', month_start),
                ('state', '=', 'posted'),
            ])
            rec.monthly_revenue = sum(invoices.mapped('amount_total'))

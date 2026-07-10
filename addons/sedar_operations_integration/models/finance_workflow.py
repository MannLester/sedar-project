from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


DEPARTMENTS = [
    ('management', 'Management'),
    ('finance', 'Finance and Accounting'),
    ('operations', 'Tug Operations'),
    ('technical', 'Technical and Maintenance'),
    ('hsse', 'HSSE'),
    ('crewing', 'Crewing'),
    ('procurement', 'Procurement'),
    ('hr', 'Human Resources'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    sedar_job_order_id = fields.Many2one('sedar.job.order', string='Tug Job Order', copy=False, index=True)
    sedar_towage_billing_id = fields.Many2one('sedar.towage.billing', string='Towage Billing', copy=False)
    sedar_vessel_id = fields.Many2one('sedar.vessel', string='Vessel', copy=False)
    sedar_budget_id = fields.Many2one('sedar.finance.budget', string='Department Budget', copy=False, check_company=True)

    def action_post(self):
        result = super().action_post()
        for move in self.filtered(lambda item: item.move_type == 'out_invoice' and item.sedar_job_order_id):
            move.sedar_job_order_id.state = 'billed'
        self.env['sedar.finance.budget'].invalidate_model(
            ['actual_amount', 'committed_amount', 'available_amount', 'utilization_percent']
        )
        return result

    def button_draft(self):
        jobs = self.filtered(lambda item: item.move_type == 'out_invoice').mapped('sedar_job_order_id')
        result = super().button_draft()
        for job in jobs.filtered(lambda item: item.state == 'billed'):
            other_posted = self.search_count([
                ('id', 'not in', self.ids),
                ('sedar_job_order_id', '=', job.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ])
            if not other_posted:
                job.state = 'completed'
        self.env['sedar.finance.budget'].invalidate_model(
            ['actual_amount', 'committed_amount', 'available_amount', 'utilization_percent']
        )
        return result


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sedar_job_order_id = fields.Many2one('sedar.job.order', string='Tug Job Order', copy=False)
    sedar_budget_id = fields.Many2one(
        'sedar.finance.budget',
        string='Department Budget',
        copy=False,
        check_company=True,
    )

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values.update({
            'sedar_job_order_id': self.sedar_job_order_id.id,
            'sedar_vessel_id': self.sedar_vessel_id.id,
            'sedar_budget_id': self.sedar_budget_id.id,
        })
        return values


class SedarTowageBilling(models.Model):
    _inherit = 'sedar.towage.billing'

    def action_create_invoice(self):
        product = self.env.ref('sedar_operations_integration.product_towage_service')
        for billing in self:
            if billing.invoice_id:
                continue
            if billing.job_order_id.state != 'completed':
                raise UserError('Complete the tug job before creating its customer invoice.')
            quantity = billing.hours if billing.rate_basis == 'hour' else 1.0
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': billing.customer_id.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_origin': billing.job_order_id.name,
                'currency_id': billing.currency_id.id,
                'sedar_job_order_id': billing.job_order_id.id,
                'sedar_towage_billing_id': billing.id,
                'sedar_vessel_id': billing.job_order_id.vessel_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'name': billing.name or billing.job_order_id.name,
                    'quantity': quantity,
                    'price_unit': billing.rate,
                })],
            })
            billing.invoice_id = invoice
        return self.action_open_invoice() if len(self) == 1 else True


class SedarFinanceBudget(models.Model):
    _name = 'sedar.finance.budget'
    _description = 'Department Budget'
    _order = 'date_start desc, name'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    department = fields.Selection(DEPARTMENTS, required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    account_ids = fields.Many2many('account.account', string='Budget Accounts', required=True)
    purchase_order_ids = fields.One2many('purchase.order', 'sedar_budget_id')
    planned_amount = fields.Monetary(required=True)
    actual_amount = fields.Monetary(compute='_compute_amounts')
    committed_amount = fields.Monetary(compute='_compute_amounts')
    available_amount = fields.Monetary(compute='_compute_amounts')
    utilization_percent = fields.Float(compute='_compute_amounts')
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approval_date = fields.Date(readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('closed', 'Closed')],
        default='draft',
        required=True,
    )
    notes = fields.Text()

    @api.depends(
        'account_ids',
        'date_start',
        'date_end',
        'planned_amount',
        'purchase_order_ids.state',
        'purchase_order_ids.date_order',
        'purchase_order_ids.currency_id',
        'purchase_order_ids.order_line.product_qty',
        'purchase_order_ids.order_line.price_subtotal',
        'purchase_order_ids.order_line.invoice_lines.move_id.state',
        'purchase_order_ids.order_line.invoice_lines.move_id.move_type',
        'purchase_order_ids.order_line.invoice_lines.quantity',
    )
    def _compute_amounts(self):
        for budget in self:
            lines = self.env['account.move.line'].search([
                ('parent_state', '=', 'posted'),
                ('account_id', 'in', budget.account_ids.ids),
                ('date', '>=', budget.date_start),
                ('date', '<=', budget.date_end),
                ('company_id', '=', budget.company_id.id),
            ]) if budget.account_ids and budget.date_start and budget.date_end else self.env['account.move.line']
            budget.actual_amount = sum(lines.mapped('balance')) if lines else 0.0
            purchase_orders = self.env['purchase.order'].search([
                ('sedar_budget_id', '=', budget.id),
                ('company_id', '=', budget.company_id.id),
                ('state', 'in', ('purchase', 'done')),
                ('date_order', '>=', budget.date_start),
                ('date_order', '<', budget.date_end + relativedelta(days=1)),
            ]) if budget.date_start and budget.date_end else self.env['purchase.order']
            committed_amount = 0.0
            for order in purchase_orders:
                for line in order.order_line.filtered(lambda item: not item.display_type and item.product_qty):
                    posted_quantity = sum(
                        invoice_line.quantity * (1 if invoice_line.move_id.move_type == 'in_invoice' else -1)
                        for invoice_line in line.invoice_lines.filtered(lambda item: item.move_id.state == 'posted')
                    )
                    remaining_subtotal = line.price_subtotal * max(line.product_qty - posted_quantity, 0.0) / line.product_qty
                    committed_amount += order.currency_id._convert(
                        remaining_subtotal,
                        budget.currency_id,
                        budget.company_id,
                        fields.Date.to_date(order.date_order),
                    )
            budget.committed_amount = committed_amount
            used = budget.actual_amount + budget.committed_amount
            budget.available_amount = budget.planned_amount - used
            budget.utilization_percent = used / budget.planned_amount * 100 if budget.planned_amount else 0.0

    @api.constrains('date_start', 'date_end', 'planned_amount')
    def _check_budget(self):
        for budget in self:
            if budget.date_end < budget.date_start:
                raise ValidationError('Budget end date cannot be before its start date.')
            if budget.planned_amount <= 0:
                raise ValidationError('Planned budget must be greater than zero.')

    def action_submit(self):
        self.filtered(lambda item: item.state == 'draft').write({'state': 'submitted'})

    def action_approve(self):
        self.filtered(lambda item: item.state == 'submitted').write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Date.context_today(self),
        })

    def action_close(self):
        self.filtered(lambda item: item.state == 'approved').write({'state': 'closed'})


class SedarCashForecast(models.Model):
    _name = 'sedar.cash.forecast'
    _description = 'Cash Flow Forecast'
    _order = 'forecast_date, id'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    forecast_date = fields.Date(required=True)
    flow_type = fields.Selection([('inflow', 'Cash Inflow'), ('outflow', 'Cash Outflow')], required=True)
    category = fields.Selection(
        [('customer', 'Customer Collection'), ('supplier', 'Supplier Payment'), ('payroll', 'Payroll'),
         ('tax', 'Tax'), ('capital', 'Capital Expenditure'), ('other', 'Other')],
        required=True,
    )
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner')
    move_id = fields.Many2one('account.move', string='Related Invoice or Bill')
    state = fields.Selection([('planned', 'Planned'), ('realized', 'Realized'), ('cancelled', 'Cancelled')], default='planned', required=True)
    notes = fields.Text()

    @api.constrains('amount')
    def _check_amount(self):
        if any(item.amount <= 0 for item in self):
            raise ValidationError('Cash forecast amount must be greater than zero.')

    def action_realize(self):
        self.filtered(lambda item: item.state == 'planned').write({'state': 'realized'})

    def action_cancel(self):
        self.filtered(lambda item: item.state == 'planned').write({'state': 'cancelled'})


class SedarFixedAsset(models.Model):
    _name = 'sedar.fixed.asset'
    _description = 'Fixed Asset Register'
    _order = 'acquisition_date desc, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    vessel_id = fields.Many2one('sedar.vessel')
    acquisition_date = fields.Date(required=True)
    original_value = fields.Monetary(required=True)
    salvage_value = fields.Monetary(default=0.0)
    useful_life_months = fields.Integer(required=True, default=60)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)
    journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'general')], check_company=True)
    asset_account_id = fields.Many2one('account.account', check_company=True)
    depreciation_account_id = fields.Many2one('account.account', check_company=True)
    expense_account_id = fields.Many2one('account.account', check_company=True)
    depreciation_line_ids = fields.One2many('sedar.asset.depreciation.line', 'asset_id')
    accumulated_depreciation = fields.Monetary(compute='_compute_asset_values')
    book_value = fields.Monetary(compute='_compute_asset_values')
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('disposed', 'Disposed')], default='draft', required=True)
    disposal_date = fields.Date()
    notes = fields.Text()

    _sql_constraints = [('fixed_asset_code_unique', 'unique(code)', 'Asset code must be unique.')]

    @api.depends('depreciation_line_ids.move_id.state', 'original_value', 'salvage_value')
    def _compute_asset_values(self):
        for asset in self:
            asset.accumulated_depreciation = sum(asset.depreciation_line_ids.filtered(lambda line: line.move_id.state == 'posted').mapped('amount'))
            asset.book_value = asset.original_value - asset.accumulated_depreciation

    @api.constrains('original_value', 'salvage_value', 'useful_life_months')
    def _check_asset_values(self):
        for asset in self:
            if asset.original_value <= 0 or asset.useful_life_months <= 0:
                raise ValidationError('Asset value and useful life must be greater than zero.')
            if asset.salvage_value < 0 or asset.salvage_value >= asset.original_value:
                raise ValidationError('Salvage value must be zero or less than original value.')

    def action_activate(self):
        for asset in self:
            if asset.state != 'draft':
                continue
            if asset.depreciation_line_ids:
                raise UserError('A depreciation schedule already exists for this asset.')
            monthly = (asset.original_value - asset.salvage_value) / asset.useful_life_months
            amounts = [asset.currency_id.round(monthly)] * asset.useful_life_months
            amounts[-1] += asset.original_value - asset.salvage_value - sum(amounts)
            asset.depreciation_line_ids = [
                (0, 0, {
                    'depreciation_date': asset.acquisition_date + relativedelta(months=index + 1),
                    'amount': amount,
                })
                for index, amount in enumerate(amounts)
            ]
            asset.state = 'active'

    def action_post_due_depreciation(self):
        today = fields.Date.context_today(self)
        for asset in self:
            if not all((asset.journal_id, asset.depreciation_account_id, asset.expense_account_id)):
                raise UserError('Set the depreciation journal, accumulated depreciation account, and expense account.')
            for line in asset.depreciation_line_ids.filtered(lambda item: not item.move_id and item.depreciation_date <= today):
                line.move_id = self.env['account.move'].create({
                    'date': line.depreciation_date,
                    'journal_id': asset.journal_id.id,
                    'company_id': asset.company_id.id,
                    'ref': '%s depreciation' % asset.code,
                    'line_ids': [
                        (0, 0, {'name': asset.name, 'account_id': asset.expense_account_id.id, 'debit': line.amount}),
                        (0, 0, {'name': asset.name, 'account_id': asset.depreciation_account_id.id, 'credit': line.amount}),
                    ],
                })
                line.move_id.action_post()

    def action_dispose(self):
        self.write({'state': 'disposed', 'disposal_date': fields.Date.context_today(self)})


class SedarAssetDepreciationLine(models.Model):
    _name = 'sedar.asset.depreciation.line'
    _description = 'Asset Depreciation Schedule'
    _order = 'depreciation_date'

    asset_id = fields.Many2one('sedar.fixed.asset', required=True, ondelete='cascade')
    depreciation_date = fields.Date(required=True)
    amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='asset_id.currency_id')
    move_id = fields.Many2one('account.move', readonly=True)


class SedarPayrollAllocation(models.Model):
    _name = 'sedar.payroll.allocation'
    _description = 'Crew Payroll Cost Allocation'
    _order = 'work_date desc, id desc'

    work_date = fields.Date(default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    job_order_id = fields.Many2one('sedar.job.order', required=True)
    crew_id = fields.Many2one('sedar.crew.member', required=True)
    employee_id = fields.Many2one(related='crew_id.employee_id', store=True)
    payroll_reference = fields.Char(related='crew_id.payroll_reference', store=True)
    regular_hours = fields.Float(default=8.0, required=True)
    overtime_hours = fields.Float(default=0.0)
    hourly_rate = fields.Monetary(required=True)
    overtime_rate = fields.Monetary(required=True)
    amount = fields.Monetary(compute='_compute_amount', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'), ('posted', 'Posted to Cost')], default='draft', required=True)
    approved_by_id = fields.Many2one('res.users', readonly=True)

    @api.depends('regular_hours', 'overtime_hours', 'hourly_rate', 'overtime_rate')
    def _compute_amount(self):
        for allocation in self:
            allocation.amount = allocation.regular_hours * allocation.hourly_rate + allocation.overtime_hours * allocation.overtime_rate

    @api.constrains('regular_hours', 'overtime_hours', 'hourly_rate', 'overtime_rate')
    def _check_payroll_values(self):
        for allocation in self:
            if min(allocation.regular_hours, allocation.overtime_hours, allocation.hourly_rate, allocation.overtime_rate) < 0:
                raise ValidationError('Payroll hours and rates cannot be negative.')

    def action_approve(self):
        self.filtered(lambda item: item.state == 'draft').write({'state': 'approved', 'approved_by_id': self.env.user.id})

    def action_post_cost(self):
        self.filtered(lambda item: item.state == 'approved').write({'state': 'posted'})


class SedarJobOrder(models.Model):
    _inherit = 'sedar.job.order'

    posted_revenue = fields.Monetary(compute='_compute_financials', currency_field='currency_id')
    fuel_cost_actual = fields.Monetary(compute='_compute_financials', currency_field='currency_id')
    vendor_bill_cost = fields.Monetary(compute='_compute_financials', currency_field='currency_id')
    crew_cost_actual = fields.Monetary(compute='_compute_financials', currency_field='currency_id')
    total_actual_cost = fields.Monetary(compute='_compute_financials', currency_field='currency_id')
    actual_gross_profit = fields.Monetary(compute='_compute_financials', currency_field='currency_id')
    gross_margin_percent = fields.Float(compute='_compute_financials')
    payroll_allocation_ids = fields.One2many('sedar.payroll.allocation', 'job_order_id')

    def _compute_financials(self):
        for job in self:
            invoices = self.env['account.move'].search([
                ('sedar_job_order_id', '=', job.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
            ])
            bills = self.env['account.move'].search([
                ('sedar_job_order_id', '=', job.id),
                ('move_type', 'in', ('in_invoice', 'in_refund')),
                ('state', '=', 'posted'),
            ])
            conversion_date = fields.Date.context_today(job)

            def job_currency_amount(amount, currency, date=False):
                return currency._convert(amount, job.currency_id, self.env.company, date or conversion_date)

            job.posted_revenue = sum(
                job_currency_amount(
                    move.amount_untaxed * (1 if move.move_type == 'out_invoice' else -1),
                    move.currency_id,
                    move.invoice_date or move.date,
                )
                for move in invoices
            )
            job.fuel_cost_actual = sum(
                job_currency_amount(log.cost, log.currency_id, fields.Date.to_date(log.date))
                for log in job.fuel_log_ids
            )
            job.vendor_bill_cost = sum(
                job_currency_amount(
                    move.amount_untaxed * (1 if move.move_type == 'in_invoice' else -1),
                    move.currency_id,
                    move.invoice_date or move.date,
                )
                for move in bills
            )
            job.crew_cost_actual = sum(
                job_currency_amount(allocation.amount, allocation.currency_id, allocation.work_date)
                for allocation in job.payroll_allocation_ids.filtered(lambda item: item.state == 'posted')
            )
            job.total_actual_cost = job.fuel_cost_actual + job.vendor_bill_cost + job.crew_cost_actual
            job.actual_gross_profit = job.posted_revenue - job.total_actual_cost
            job.gross_margin_percent = job.actual_gross_profit / job.posted_revenue * 100 if job.posted_revenue else 0.0


class SedarDashboard(models.Model):
    _inherit = 'sedar.dashboard'

    accounts_receivable = fields.Monetary(compute='_compute_finance_kpis', currency_field='currency_id')
    accounts_payable = fields.Monetary(compute='_compute_finance_kpis', currency_field='currency_id')
    cash_balance = fields.Monetary(compute='_compute_finance_kpis', currency_field='currency_id')
    forecast_net_cash = fields.Monetary(compute='_compute_finance_kpis', currency_field='currency_id')
    unbilled_jobs = fields.Integer(compute='_compute_finance_kpis')
    total_job_profit = fields.Monetary(compute='_compute_finance_kpis', currency_field='currency_id')
    asset_book_value = fields.Monetary(compute='_compute_finance_kpis', currency_field='currency_id')

    def _compute_finance_kpis(self):
        today = fields.Date.context_today(self)
        horizon = today + relativedelta(days=30)
        for dashboard in self:
            company = self.env.company
            receivables = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
            ])
            payables = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('move_type', 'in', ('in_invoice', 'in_refund')),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
            ])
            liquidity_lines = self.env['account.move.line'].search([
                ('company_id', '=', company.id),
                ('parent_state', '=', 'posted'),
                ('account_id.account_type', '=', 'asset_cash'),
            ])
            forecasts = self.env['sedar.cash.forecast'].search([
                ('company_id', '=', company.id),
                ('state', '=', 'planned'),
                ('forecast_date', '>=', today),
                ('forecast_date', '<=', horizon),
            ])
            jobs = self.env['sedar.job.order'].search([])
            assets = self.env['sedar.fixed.asset'].search([('company_id', '=', company.id), ('state', '=', 'active')])
            dashboard.accounts_receivable = sum(
                move.amount_residual * (1 if move.move_type == 'out_invoice' else -1)
                for move in receivables
            )
            dashboard.accounts_payable = sum(
                move.amount_residual * (1 if move.move_type == 'in_invoice' else -1)
                for move in payables
            )
            dashboard.cash_balance = sum(liquidity_lines.mapped('balance'))
            dashboard.forecast_net_cash = sum(item.amount * (1 if item.flow_type == 'inflow' else -1) for item in forecasts)
            dashboard.unbilled_jobs = self.env['sedar.job.order'].search_count([('state', '=', 'completed')])
            dashboard.total_job_profit = sum(jobs.mapped('actual_gross_profit'))
            dashboard.asset_book_value = sum(assets.mapped('book_value'))

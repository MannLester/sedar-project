from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SedarExpenseCategory(models.Model):
    _name = "sedar.finance.expense.category"
    _description = "Finance Expense Category"
    _order = "name"

    name = fields.Char(required=True)
    account_id = fields.Many2one(
        "account.account", required=True, check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_depreciation', 'expense_direct_cost'))]",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_company_unique", "unique(name, company_id)", "The category name must be unique per company."),
    ]


class SedarPettyCashFund(models.Model):
    _name = "sedar.finance.petty.fund"
    _description = "Petty Cash Fund"
    _order = "name"

    name = fields.Char(required=True)
    journal_id = fields.Many2one(
        "account.journal", required=True, check_company=True,
        domain="[('type', 'in', ('cash', 'bank'))]",
    )
    account_id = fields.Many2one(
        "account.account", required=True, check_company=True,
        domain="[('account_type', '=', 'asset_cash')]",
    )
    advance_account_id = fields.Many2one(
        "account.account", required=True, check_company=True,
        domain="[('account_type', 'in', ('asset_receivable', 'asset_current'))]",
        help="Receivable account used when employee advances are released from this fund.",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)

    @api.constrains("journal_id", "account_id", "advance_account_id", "company_id")
    def _check_company_links(self):
        for fund in self:
            if any(item.company_id != fund.company_id for item in (fund.journal_id, fund.account_id, fund.advance_account_id)):
                raise ValidationError(_("The fund journal and accounts must belong to the fund company."))


class SedarTerminal(models.Model):
    _name = "sedar.finance.terminal"
    _description = "Billing Terminal"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [("terminal_code_unique", "unique(code)", "Terminal code must be unique.")]


class SedarService(models.Model):
    _name = "sedar.finance.service"
    _description = "Billable Service"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    income_account_id = fields.Many2one(
        "account.account", required=True, check_company=True,
        domain="[('account_type', 'in', ('income', 'income_other'))]",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [("service_code_company_unique", "unique(code, company_id)", "Service code must be unique per company.")]


class SedarTariff(models.Model):
    _name = "sedar.finance.tariff"
    _description = "Approved Client Tariff"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "effective_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    client_id = fields.Many2one("res.partner", required=True, tracking=True)
    terminal_id = fields.Many2one("sedar.finance.terminal", required=True, tracking=True)
    service_id = fields.Many2one("sedar.finance.service", required=True, tracking=True, check_company=True)
    rate_basis = fields.Selection(
        [("job", "Per Job"), ("hour", "Per Hour"), ("move", "Per Move")], required=True, default="job", tracking=True,
    )
    rate = fields.Monetary(required=True, tracking=True)
    effective_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    expiry_date = fields.Date(tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft", required=True, tracking=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)
    approved_date = fields.Datetime(readonly=True, copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.tariff") or "New"
        return super().create(vals_list)

    @api.constrains("rate", "effective_date", "expiry_date")
    def _check_values(self):
        for tariff in self:
            if tariff.rate <= 0:
                raise ValidationError(_("Tariff rate must be greater than zero."))
            if tariff.expiry_date and tariff.expiry_date < tariff.effective_date:
                raise ValidationError(_("Tariff expiry cannot be before its effective date."))

    def action_submit(self):
        self.filtered(lambda record: record.state in ("draft", "rejected")).write({"state": "submitted"})

    def action_approve(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may approve tariffs."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({
            "state": "approved", "approved_by_id": self.env.user.id, "approved_date": fields.Datetime.now(),
        })

    def action_reject(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may reject tariffs."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({"state": "rejected"})

    def write(self, values):
        if values.get("state") in ("approved", "rejected") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the Finance Manager approval actions to change this state."))
        locked = {"client_id", "terminal_id", "service_id", "rate_basis", "rate", "effective_date", "expiry_date", "company_id"}
        if locked.intersection(values) and any(record.state == "approved" for record in self):
            raise UserError(_("An approved tariff is locked. Create a new effective tariff instead."))
        return super().write(values)


class SedarAgentRebateRate(models.Model):
    _name = "sedar.finance.agent.rebate.rate"
    _description = "Approved Agent Rebate Rate"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "effective_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    agent_id = fields.Many2one("res.partner", required=True, tracking=True)
    service_id = fields.Many2one("sedar.finance.service", required=True, tracking=True, check_company=True)
    rate_percent = fields.Float(required=True, tracking=True)
    effective_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    expiry_date = fields.Date(tracking=True)
    expense_account_id = fields.Many2one(
        "account.account", required=True, check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_direct_cost'))]",
    )
    payable_account_id = fields.Many2one(
        "account.account", required=True, check_company=True,
        domain="[('account_type', '=', 'liability_payable')]",
    )
    journal_id = fields.Many2one(
        "account.journal", required=True, check_company=True, domain="[('type', '=', 'general')]",
        help="General journal used to accrue the rebate expense and payable.",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft", required=True, tracking=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)
    approved_date = fields.Datetime(readonly=True, copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.rebate") or "New"
        return super().create(vals_list)

    @api.constrains("rate_percent", "effective_date", "expiry_date")
    def _check_values(self):
        for rate in self:
            if rate.rate_percent <= 0 or rate.rate_percent > 100:
                raise ValidationError(_("Rebate percent must be greater than zero and no more than 100."))
            if rate.expiry_date and rate.expiry_date < rate.effective_date:
                raise ValidationError(_("Rebate expiry cannot be before its effective date."))

    def action_submit(self):
        self.filtered(lambda record: record.state in ("draft", "rejected")).write({"state": "submitted"})

    def action_approve(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may approve rebate rates."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({
            "state": "approved", "approved_by_id": self.env.user.id, "approved_date": fields.Datetime.now(),
        })

    def action_reject(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may reject rebate rates."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({"state": "rejected"})

    def write(self, values):
        if values.get("state") in ("approved", "rejected") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the Finance Manager approval actions to change this state."))
        locked = {
            "agent_id", "service_id", "rate_percent", "effective_date", "expiry_date",
            "expense_account_id", "payable_account_id", "journal_id", "company_id",
        }
        if locked.intersection(values) and any(record.state == "approved" for record in self):
            raise UserError(_("An approved rebate rate is locked. Create a new effective rate instead."))
        return super().write(values)

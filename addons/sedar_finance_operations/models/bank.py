from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    sedar_statement_balance = fields.Monetary(string="Manual Statement Balance", currency_field="currency_id")
    sedar_statement_date = fields.Date(string="Statement Date")
    sedar_posted_book_balance = fields.Monetary(compute="_compute_sedar_bank_control", currency_field="currency_id")
    sedar_outstanding_checks = fields.Monetary(compute="_compute_sedar_bank_control", currency_field="currency_id")
    sedar_available_cash = fields.Monetary(compute="_compute_sedar_bank_control", currency_field="currency_id")

    def _compute_sedar_bank_control(self):
        line_model = self.env["account.move.line"]
        check_model = self.env["sedar.finance.disbursement"]
        for journal in self:
            accounts = journal.default_account_id
            lines = line_model.search([
                ("company_id", "=", journal.company_id.id), ("parent_state", "=", "posted"),
                ("account_id", "in", accounts.ids),
            ]) if accounts else line_model
            checks = check_model.search([
                ("journal_id", "=", journal.id), ("state", "=", "released"),
                ("payment_type", "=", "check"), ("check_status", "in", ("outstanding", "stale")),
            ])
            journal.sedar_posted_book_balance = sum(lines.mapped("balance")) if lines else 0.0
            journal.sedar_outstanding_checks = sum(checks.mapped("amount"))
            journal.sedar_available_cash = journal.sedar_statement_balance - journal.sedar_outstanding_checks


class SedarBankAdjustment(models.Model):
    _name = "sedar.finance.bank.adjustment"
    _description = "Bank Charge or Interest Adjustment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    adjustment_type = fields.Selection([("charge", "Bank Charge"), ("interest", "Interest Income")],
                                       required=True, default="charge", tracking=True)
    journal_id = fields.Many2one("account.journal", required=True, check_company=True, tracking=True,
                                 domain="[('type', '=', 'bank')]")
    counterpart_account_id = fields.Many2one("account.account", required=True, check_company=True, tracking=True)
    amount = fields.Monetary(required=True, tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    description = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    state = fields.Selection([("draft", "Draft"), ("posted", "Posted")], default="draft", required=True, tracking=True)
    move_id = fields.Many2one("account.move", readonly=True, copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.bank.adjustment") or "New"
        return super().create(vals_list)

    def write(self, values):
        if values.get("state") == "posted" and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use Post Adjustment to create the ledger entry."))
        if not self.env.context.get("sedar_posting") and set(values) - {"message_follower_ids", "message_partner_ids"} and any(
            record.state == "posted" for record in self
        ):
            raise UserError(_("A posted bank adjustment is locked."))
        return super().write(values)

    @api.constrains("amount")
    def _check_amount(self):
        if any(record.amount <= 0 for record in self):
            raise ValidationError(_("Adjustment amount must be greater than zero."))

    def action_post(self):
        for record in self.filtered(lambda item: item.state == "draft"):
            if record.journal_id.company_id != record.company_id or record.counterpart_account_id.company_id != record.company_id:
                raise UserError(_("The journal and counterpart account must belong to the adjustment company."))
            cash_account = record.journal_id.default_account_id
            if not cash_account:
                raise UserError(_("Set a default account on the bank journal."))
            charge = record.adjustment_type == "charge"
            move = self.env["account.move"].create({
                "date": record.date, "journal_id": record.journal_id.id, "company_id": record.company_id.id,
                "ref": record.name, "sedar_bank_adjustment_id": record.id,
                "line_ids": [
                    (0, 0, {"name": record.description, "account_id": record.counterpart_account_id.id,
                            "debit": record.amount if charge else 0.0, "credit": 0.0 if charge else record.amount}),
                    (0, 0, {"name": record.description, "account_id": cash_account.id,
                            "debit": 0.0 if charge else record.amount, "credit": record.amount if charge else 0.0}),
                ],
            })
            move.action_post()
            record.with_context(sedar_posting=True, sedar_workflow=True).write({
                "move_id": move.id, "state": "posted",
            })

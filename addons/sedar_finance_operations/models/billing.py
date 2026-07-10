from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SedarJobOrder(models.Model):
    _inherit = "sedar.job.order"

    terminal_id = fields.Many2one("sedar.finance.terminal")
    service_id = fields.Many2one("sedar.finance.service")
    move_count = fields.Integer(string="Billable Moves", default=1)
    billable_hours = fields.Float(default=1.0)
    agent_id = fields.Many2one("res.partner", string="Agent")

    @api.constrains("move_count", "billable_hours")
    def _check_billable_values(self):
        for job in self:
            if job.move_count < 0 or job.billable_hours < 0:
                raise ValidationError(_("Billable moves and hours cannot be negative."))


class SedarTowageBilling(models.Model):
    _inherit = "sedar.towage.billing"

    rate_basis = fields.Selection(selection_add=[("move", "Per Move")], ondelete={"move": "set default"})
    tariff_id = fields.Many2one(
        "sedar.finance.tariff", string="Approved Tariff",
        domain="[('state', '=', 'approved')]",
    )
    terminal_id = fields.Many2one(related="job_order_id.terminal_id", store=True, readonly=True)
    service_id = fields.Many2one(related="job_order_id.service_id", store=True, readonly=True)
    agent_id = fields.Many2one(related="job_order_id.agent_id", store=True, readonly=True)
    rebate_rate_id = fields.Many2one("sedar.finance.agent.rebate.rate", readonly=True)
    rebate_amount = fields.Monetary(compute="_compute_rebate", store=True, currency_field="currency_id")
    rebate_move_id = fields.Many2one("account.move", readonly=True, copy=False)

    @api.depends("rate", "rate_basis", "hours", "job_order_id.move_count", "tariff_id")
    def _compute_amount(self):
        for billing in self:
            quantity = billing.hours if billing.rate_basis == "hour" else (
                billing.job_order_id.move_count if billing.rate_basis == "move" else 1.0
            )
            billing.amount = billing.rate * quantity

    @api.depends("amount", "rebate_rate_id.rate_percent")
    def _compute_rebate(self):
        for billing in self:
            billing.rebate_amount = billing.amount * billing.rebate_rate_id.rate_percent / 100.0

    @api.onchange("job_order_id")
    def _onchange_job_order_finance(self):
        if self.job_order_id:
            self.hours = self.job_order_id.billable_hours
            self.tariff_id = self._find_tariff_for_job(self.job_order_id)

    def _find_tariff_for_job(self, job):
        bill_date = fields.Date.context_today(self)
        return self.env["sedar.finance.tariff"].search([
            ("client_id", "=", job.customer_id.id),
            ("terminal_id", "=", job.terminal_id.id),
            ("service_id", "=", job.service_id.id),
            ("company_id", "=", self.env.company.id),
            ("state", "=", "approved"),
            ("effective_date", "<=", bill_date),
            "|", ("expiry_date", "=", False), ("expiry_date", ">=", bill_date),
        ], order="effective_date desc, id desc", limit=1)

    @api.onchange("tariff_id")
    def _onchange_tariff_id(self):
        if self.tariff_id:
            self.rate_basis = self.tariff_id.rate_basis
            self.rate = self.tariff_id.rate
            self.currency_id = self.tariff_id.currency_id

    def _check_tariff(self):
        self.ensure_one()
        tariff = self.tariff_id
        bill_date = fields.Date.context_today(self)
        if not tariff or tariff.state != "approved":
            raise UserError(_("Select an approved tariff."))
        if tariff.company_id != self.env.company:
            raise UserError(_("The tariff must belong to the active company."))
        if tariff.client_id != self.customer_id or tariff.terminal_id != self.terminal_id or tariff.service_id != self.service_id:
            raise UserError(_("The tariff must match the billing client, terminal, and service."))
        if tariff.effective_date > bill_date or (tariff.expiry_date and tariff.expiry_date < bill_date):
            raise UserError(_("The tariff is not effective on the billing date."))

    @api.constrains("tariff_id", "job_order_id")
    def _check_tariff_links(self):
        for billing in self.filtered("tariff_id"):
            billing._check_tariff()

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("job_order_id"):
                job = self.env["sedar.job.order"].browse(values["job_order_id"])
                tariff = self.env["sedar.finance.tariff"].browse(values.get("tariff_id")) or self._find_tariff_for_job(job)
                if tariff:
                    values.update({
                        "tariff_id": tariff.id,
                        "rate_basis": tariff.rate_basis,
                        "rate": tariff.rate,
                        "currency_id": tariff.currency_id.id,
                        "hours": job.billable_hours,
                    })
        records = super().create(vals_list)
        for billing in records.filtered("tariff_id"):
            billing._apply_tariff_values()
        return records

    def write(self, values):
        protected = {"rate", "rate_basis", "currency_id", "tariff_id"}
        if protected.intersection(values) and any(record.invoice_id for record in self):
            raise UserError(_("Invoiced billing rates are locked."))
        if {"rate", "rate_basis", "currency_id"}.intersection(values) and any(record.tariff_id for record in self):
            if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
                raise UserError(_("Cashiers and encoders cannot change a selected approved tariff rate."))
        result = super().write(values)
        if "tariff_id" in values:
            for billing in self.filtered("tariff_id"):
                billing._apply_tariff_values()
        return result

    def _apply_tariff_values(self):
        self.ensure_one()
        self._check_tariff()
        super(SedarTowageBilling, self).write({
            "rate_basis": self.tariff_id.rate_basis, "rate": self.tariff_id.rate,
            "currency_id": self.tariff_id.currency_id.id,
            "hours": self.job_order_id.billable_hours,
        })

    def _find_rebate_rate(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.env["sedar.finance.agent.rebate.rate"].search([
            ("agent_id", "=", self.agent_id.id), ("service_id", "=", self.service_id.id),
            ("company_id", "=", self.env.company.id), ("state", "=", "approved"),
            ("effective_date", "<=", today), "|", ("expiry_date", "=", False), ("expiry_date", ">=", today),
        ], order="effective_date desc, id desc", limit=1)

    def action_confirm_and_invoice(self):
        for billing in self:
            if billing.invoice_id:
                continue
            billing._check_tariff()
            if billing.job_order_id.state != "completed":
                raise UserError(_("Complete the tug job before confirming its invoice."))
            quantity = billing.hours if billing.rate_basis == "hour" else (
                billing.job_order_id.move_count if billing.rate_basis == "move" else 1.0
            )
            if quantity <= 0:
                raise UserError(_("The billable quantity must be greater than zero."))
            invoice = self.env["account.move"].create({
                "move_type": "out_invoice", "partner_id": billing.customer_id.id,
                "invoice_date": fields.Date.context_today(self), "invoice_origin": billing.job_order_id.name,
                "currency_id": billing.currency_id.id, "sedar_job_order_id": billing.job_order_id.id,
                "sedar_towage_billing_id": billing.id, "sedar_vessel_id": billing.job_order_id.vessel_id.id,
                "sedar_finance_billing_id": billing.id,
                "invoice_line_ids": [(0, 0, {
                    "name": "%s - %s" % (billing.service_id.name, billing.job_order_id.name),
                    "quantity": quantity, "price_unit": billing.rate,
                    "account_id": billing.service_id.income_account_id.id,
                })],
            })
            invoice.action_post()
            values = {"invoice_id": invoice.id}
            rebate_rate = billing._find_rebate_rate() if billing.agent_id else False
            if rebate_rate:
                rebate_amount = billing.currency_id.round(billing.amount * rebate_rate.rate_percent / 100.0)
                rebate_move = self.env["account.move"].create({
                    "date": invoice.date, "journal_id": rebate_rate.journal_id.id, "company_id": rebate_rate.company_id.id,
                    "ref": _("Agent rebate for %s") % billing.name, "sedar_finance_billing_id": billing.id,
                    "sedar_job_order_id": billing.job_order_id.id, "sedar_vessel_id": billing.job_order_id.vessel_id.id,
                    "line_ids": [
                        (0, 0, {"name": billing.agent_id.name, "account_id": rebate_rate.expense_account_id.id,
                                "partner_id": billing.agent_id.id, "debit": rebate_amount}),
                        (0, 0, {"name": billing.agent_id.name, "account_id": rebate_rate.payable_account_id.id,
                                "partner_id": billing.agent_id.id, "credit": rebate_amount}),
                    ],
                })
                rebate_move.action_post()
                values.update({"rebate_rate_id": rebate_rate.id, "rebate_move_id": rebate_move.id})
            billing.write(values)
        return self.action_open_invoice() if len(self) == 1 else True

    def action_create_invoice(self):
        return self.action_confirm_and_invoice()

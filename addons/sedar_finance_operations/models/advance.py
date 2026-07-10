from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SedarCashAdvance(models.Model):
    _name = "sedar.finance.cash.advance"
    _description = "Employee Cash Advance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date, id"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    purpose = fields.Char(required=True, tracking=True)
    fund_id = fields.Many2one("sedar.finance.petty.fund", required=True, tracking=True, check_company=True)
    advance_account_id = fields.Many2one(related="fund_id.advance_account_id", store=True, readonly=True)
    amount = fields.Monetary(required=True, tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
         ("released", "Released"), ("partial", "Partially Liquidated"), ("liquidated", "Liquidated"),
         ("rejected", "Rejected")], default="draft", required=True, tracking=True,
    )
    move_id = fields.Many2one("account.move", readonly=True, copy=False, tracking=True)
    liquidation_ids = fields.One2many("sedar.finance.advance.liquidation", "advance_id")
    liquidated_amount = fields.Monetary(compute="_compute_outstanding", store=True)
    outstanding_amount = fields.Monetary(compute="_compute_outstanding", store=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)

    @api.depends("amount", "liquidation_ids.state", "liquidation_ids.total_settlement")
    def _compute_outstanding(self):
        for advance in self:
            advance.liquidated_amount = sum(
                advance.liquidation_ids.filtered(lambda item: item.state == "approved").mapped("total_settlement")
            )
            advance.outstanding_amount = max(advance.amount - advance.liquidated_amount, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.cash.advance") or "New"
        return super().create(vals_list)

    def write(self, values):
        if values.get("state") in ("approved", "released", "partial", "liquidated", "rejected") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the Finance Manager workflow actions to change this state."))
        if not self.env.context.get("sedar_posting") and set(values) - {"state", "message_follower_ids", "message_partner_ids"} and any(
            record.move_id and record.move_id.state == "posted" for record in self
        ):
            raise UserError(_("A released cash advance is locked."))
        return super().write(values)

    @api.constrains("amount")
    def _check_amount(self):
        if any(record.amount <= 0 for record in self):
            raise ValidationError(_("Advance amount must be greater than zero."))

    def action_submit(self):
        self.filtered(lambda record: record.state in ("draft", "rejected")).write({"state": "submitted"})

    def action_approve(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may approve advances."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({
            "state": "approved", "approved_by_id": self.env.user.id,
        })

    def action_release(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may release advances."))
        for record in self.filtered(lambda item: item.state == "approved"):
            if record.fund_id.company_id != record.company_id or record.advance_account_id.company_id != record.company_id:
                raise UserError(_("The fund and advance account must belong to the advance company."))
            move = self.env["account.move"].create({
                "date": record.date, "journal_id": record.fund_id.journal_id.id, "company_id": record.company_id.id,
                "ref": record.name, "sedar_cash_advance_id": record.id,
                "line_ids": [
                    (0, 0, {"name": record.purpose, "account_id": record.advance_account_id.id,
                            "partner_id": record.employee_id.work_contact_id.id, "debit": record.amount}),
                    (0, 0, {"name": record.purpose, "account_id": record.fund_id.account_id.id,
                            "partner_id": record.employee_id.work_contact_id.id, "credit": record.amount}),
                ],
            })
            move.action_post()
            record.with_context(sedar_posting=True, sedar_workflow=True).write({"move_id": move.id, "state": "released"})

    def action_reject(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may reject advances."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({"state": "rejected"})


class SedarAdvanceLiquidation(models.Model):
    _name = "sedar.finance.advance.liquidation"
    _description = "Cash Advance Liquidation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    advance_id = fields.Many2one("sedar.finance.cash.advance", required=True, tracking=True, check_company=True)
    employee_id = fields.Many2one(related="advance_id.employee_id", store=True, readonly=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    line_ids = fields.One2many("sedar.finance.advance.liquidation.line", "liquidation_id", copy=True)
    cash_returned = fields.Monetary(default=0.0, tracking=True)
    expense_amount = fields.Monetary(compute="_compute_amounts", store=True)
    total_settlement = fields.Monetary(compute="_compute_amounts", store=True)
    advance_outstanding = fields.Monetary(related="advance_id.outstanding_amount", readonly=True)
    fund_id = fields.Many2one(related="advance_id.fund_id", store=True, readonly=True)
    vessel_id = fields.Many2one("sedar.vessel", tracking=True)
    job_order_id = fields.Many2one("sedar.job.order", string="Job", tracking=True)
    maintenance_request_id = fields.Many2one("maintenance.request", string="Maintenance Work Order", tracking=True)
    company_id = fields.Many2one(related="advance_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft", required=True, tracking=True,
    )
    move_id = fields.Many2one("account.move", readonly=True, copy=False, tracking=True)

    @api.depends("line_ids.amount", "cash_returned")
    def _compute_amounts(self):
        for liquidation in self:
            liquidation.expense_amount = sum(liquidation.line_ids.mapped("amount"))
            liquidation.total_settlement = liquidation.expense_amount + liquidation.cash_returned

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.liquidation") or "New"
        return super().create(vals_list)

    def write(self, values):
        if values.get("state") in ("approved", "rejected") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the Finance Manager workflow actions to change this state."))
        if not self.env.context.get("sedar_posting") and set(values) - {"message_follower_ids", "message_partner_ids"} and any(
            record.move_id and record.move_id.state == "posted" for record in self
        ):
            raise UserError(_("An approved liquidation is locked."))
        return super().write(values)

    @api.constrains("cash_returned", "line_ids")
    def _check_amounts(self):
        for liquidation in self:
            if liquidation.cash_returned < 0 or any(line.amount <= 0 for line in liquidation.line_ids):
                raise ValidationError(_("Liquidation line amounts must be positive and cash returned cannot be negative."))

    def _check_fifo(self):
        self.ensure_one()
        oldest = self.env["sedar.finance.cash.advance"].search([
            ("employee_id", "=", self.employee_id.id), ("company_id", "=", self.company_id.id),
            ("state", "in", ("released", "partial")), ("outstanding_amount", ">", 0),
        ], order="date, id", limit=1)
        if oldest != self.advance_id:
            raise UserError(_("Liquidate the employee's oldest outstanding advance first: %s") % oldest.display_name)

    def action_submit(self):
        for record in self.filtered(lambda item: item.state in ("draft", "rejected")):
            record._check_fifo()
            if not record.line_ids and not record.cash_returned:
                raise UserError(_("Add expense lines or cash returned before submitting."))
            if record.total_settlement > record.advance_id.outstanding_amount:
                raise UserError(_("The liquidation cannot exceed the outstanding advance."))
            record.state = "submitted"

    def action_approve(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may approve liquidations."))
        for record in self.filtered(lambda item: item.state == "submitted"):
            record._check_fifo()
            if record.total_settlement <= 0 or record.total_settlement > record.advance_id.outstanding_amount:
                raise UserError(_("The liquidation must be positive and cannot exceed the outstanding advance."))
            lines = [
                (0, 0, {"name": line.description or line.category_id.name, "account_id": line.category_id.account_id.id,
                        "debit": line.amount}) for line in record.line_ids
            ]
            if record.cash_returned:
                lines.append((0, 0, {"name": _("Cash returned"), "account_id": record.fund_id.account_id.id,
                                     "debit": record.cash_returned}))
            lines.append((0, 0, {"name": record.name, "account_id": record.advance_id.advance_account_id.id,
                                 "partner_id": record.employee_id.work_contact_id.id, "credit": record.total_settlement}))
            move = self.env["account.move"].create({
                "date": record.date, "journal_id": record.fund_id.journal_id.id, "company_id": record.company_id.id,
                "ref": record.name, "sedar_cash_advance_id": record.advance_id.id,
                "sedar_advance_liquidation_id": record.id, "sedar_vessel_id": record.vessel_id.id,
                "sedar_job_order_id": record.job_order_id.id,
                "sedar_maintenance_request_id": record.maintenance_request_id.id,
                "line_ids": lines,
            })
            move.action_post()
            record.with_context(sedar_posting=True, sedar_workflow=True).write({"move_id": move.id, "state": "approved"})
            outstanding = record.advance_id.outstanding_amount
            record.advance_id.with_context(sedar_workflow=True).state = (
                "liquidated" if record.currency_id.is_zero(outstanding) else "partial"
            )

    def action_reject(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may reject liquidations."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({"state": "rejected"})


class SedarAdvanceLiquidationLine(models.Model):
    _name = "sedar.finance.advance.liquidation.line"
    _description = "Cash Advance Liquidation Line"

    liquidation_id = fields.Many2one("sedar.finance.advance.liquidation", required=True, ondelete="cascade")
    category_id = fields.Many2one("sedar.finance.expense.category", required=True, check_company=True)
    description = fields.Char()
    amount = fields.Monetary(required=True)
    company_id = fields.Many2one(related="liquidation_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="liquidation_id.currency_id", readonly=True)

    @api.constrains("amount")
    def _check_amount(self):
        if any(line.amount <= 0 for line in self):
            raise ValidationError(_("Liquidation amount must be greater than zero."))

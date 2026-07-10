from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SedarPettyCashExpense(models.Model):
    _name = "sedar.finance.petty.cash"
    _description = "Petty Cash Expense"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    category_id = fields.Many2one("sedar.finance.expense.category", required=True, tracking=True, check_company=True)
    fund_id = fields.Many2one("sedar.finance.petty.fund", required=True, tracking=True, check_company=True)
    amount = fields.Monetary(required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", tracking=True)
    employee_id = fields.Many2one("hr.employee", tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    description = fields.Char(required=True, tracking=True)
    vessel_id = fields.Many2one("sedar.vessel", tracking=True)
    job_order_id = fields.Many2one("sedar.job.order", string="Job", tracking=True)
    maintenance_request_id = fields.Many2one("maintenance.request", string="Maintenance Work Order", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft", required=True, tracking=True,
    )
    move_id = fields.Many2one("account.move", readonly=True, copy=False, tracking=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)
    approved_date = fields.Datetime(readonly=True, copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.petty.cash") or "New"
        return super().create(vals_list)

    def write(self, values):
        if values.get("state") in ("approved", "rejected") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the Finance Manager workflow actions to change this state."))
        locked = set(values) - {"message_follower_ids", "message_partner_ids"}
        if not self.env.context.get("sedar_posting") and locked and any(
            record.move_id and record.move_id.state == "posted" for record in self
        ):
            raise UserError(_("A posted petty cash expense is locked."))
        return super().write(values)

    @api.constrains("amount", "date")
    def _check_values(self):
        if any(record.amount <= 0 for record in self):
            raise ValidationError(_("Petty cash amount must be greater than zero."))

    def action_submit(self):
        self.filtered(lambda record: record.state in ("draft", "rejected")).write({"state": "submitted"})

    def action_approve(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may approve petty cash expenses."))
        for record in self.filtered(lambda item: item.state == "submitted"):
            if record.category_id.company_id != record.company_id or record.fund_id.company_id != record.company_id:
                raise UserError(_("The category and fund must belong to the expense company."))
            move = self.env["account.move"].create({
                "date": record.date,
                "journal_id": record.fund_id.journal_id.id,
                "company_id": record.company_id.id,
                "ref": record.name,
                "sedar_petty_cash_id": record.id,
                "sedar_vessel_id": record.vessel_id.id,
                "sedar_job_order_id": record.job_order_id.id,
                "sedar_maintenance_request_id": record.maintenance_request_id.id,
                "line_ids": [
                    (0, 0, {"name": record.description, "account_id": record.category_id.account_id.id,
                            "partner_id": record.partner_id.id, "debit": record.amount}),
                    (0, 0, {"name": record.description, "account_id": record.fund_id.account_id.id,
                            "partner_id": record.partner_id.id, "credit": record.amount}),
                ],
            })
            move.action_post()
            record.with_context(sedar_posting=True, sedar_workflow=True).write({
                "move_id": move.id, "state": "approved", "approved_by_id": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })

    def action_reject(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may reject petty cash expenses."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({"state": "rejected"})

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SedarCollection(models.Model):
    _name = "sedar.finance.collection"
    _description = "Customer Collection Receipt"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "deposit_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    invoice_id = fields.Many2one(
        "account.move", required=True, tracking=True, check_company=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('payment_state', '!=', 'paid')]",
    )
    customer_id = fields.Many2one(related="invoice_id.partner_id", store=True, readonly=True)
    journal_id = fields.Many2one(
        "account.journal", required=True, tracking=True, check_company=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
    )
    amount = fields.Monetary(required=True, tracking=True)
    method = fields.Selection([("deposit", "Deposit"), ("check", "Check")], required=True, default="deposit", tracking=True)
    bank_reference = fields.Char(tracking=True)
    check_number = fields.Char(tracking=True)
    deposit_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", store=True, readonly=True)
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"), ("bounced", "Bounced")],
                             default="draft", required=True, tracking=True)
    payment_id = fields.Many2one("account.payment", readonly=True, copy=False, tracking=True)
    bounced_reason = fields.Text(tracking=True)
    bounced_date = fields.Date(readonly=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.collection") or "New"
        return super().create(vals_list)

    def write(self, values):
        if values.get("state") in ("confirmed", "bounced") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the collection workflow actions to change this state."))
        bounce_fields = {"state", "bounced_reason", "bounced_date", "message_follower_ids", "message_partner_ids"}
        if set(values) - bounce_fields and any(record.state in ("confirmed", "bounced") for record in self):
            raise UserError(_("A confirmed or bounced collection is locked."))
        return super().write(values)

    @api.constrains("amount", "method", "check_number")
    def _check_values(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Collection amount must be greater than zero."))
            if record.method == "check" and not record.check_number:
                raise ValidationError(_("Check number is required for check collections."))

    def action_confirm(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_officer"):
            raise UserError(_("Only a Finance Officer or Manager may confirm collections."))
        for record in self.filtered(lambda item: item.state == "draft"):
            if record.invoice_id.state != "posted" or record.invoice_id.move_type != "out_invoice":
                raise UserError(_("Select a posted customer invoice."))
            if record.amount > record.invoice_id.amount_residual:
                raise UserError(_("Collection amount cannot exceed the invoice residual."))
            if record.invoice_id.company_id != record.company_id or record.journal_id.company_id != record.company_id:
                raise UserError(_("The invoice, journal, and receipt must use the same company."))
            register = self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=record.invoice_id.ids,
            ).create({"journal_id": record.journal_id.id, "payment_date": record.deposit_date, "amount": record.amount})
            payment = register._create_payments()[:1]
            payment.write({
                "sedar_collection_id": record.id, "sedar_collection_invoice_id": record.invoice_id.id,
                "sedar_bank_reference": record.bank_reference, "sedar_check_number": record.check_number,
                "sedar_vessel_id": record.invoice_id.sedar_vessel_id.id,
                "sedar_job_order_id": record.invoice_id.sedar_job_order_id.id,
            })
            record.with_context(sedar_workflow=True).write({"payment_id": payment.id, "state": "confirmed"})

    def action_bounce(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may mark collections bounced."))
        for record in self.filtered(lambda item: item.state == "confirmed"):
            if not record.bounced_reason:
                raise UserError(_("Enter the bounced reason before marking the collection bounced."))
            record.payment_id.move_id.line_ids.remove_move_reconcile()
            record.payment_id.action_cancel()
            record.with_context(sedar_workflow=True).write({
                "state": "bounced", "bounced_date": fields.Date.context_today(self),
            })

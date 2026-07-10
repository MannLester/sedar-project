from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SedarDisbursement(models.Model):
    _name = "sedar.finance.disbursement"
    _description = "PO-backed Disbursement and Check Voucher"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    purchase_id = fields.Many2one("purchase.order", string="Purchase Order", required=True, tracking=True, check_company=True)
    bill_id = fields.Many2one(
        "account.move", string="Posted Vendor Bill", required=True, tracking=True, check_company=True,
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('payment_state', '!=', 'paid')]",
    )
    supplier_id = fields.Many2one(related="bill_id.partner_id", store=True, readonly=True)
    vessel_id = fields.Many2one(related="purchase_id.sedar_vessel_id", store=True, readonly=True)
    job_order_id = fields.Many2one(related="purchase_id.sedar_job_order_id", string="Job", store=True, readonly=True)
    maintenance_request_id = fields.Many2one(
        related="purchase_id.sedar_maintenance_request_id", string="Maintenance Work Order", store=True, readonly=True,
    )
    journal_id = fields.Many2one(
        "account.journal", required=True, tracking=True, check_company=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
    )
    amount = fields.Monetary(required=True, tracking=True)
    payment_type = fields.Selection([("cash", "Cash"), ("check", "Check")], required=True, default="check", tracking=True)
    check_number = fields.Char(tracking=True)
    check_date = fields.Date(tracking=True)
    check_status = fields.Selection(
        [("none", "Not a Check"), ("outstanding", "Outstanding"), ("cleared", "Cleared"),
         ("stale", "Stale"), ("void", "Void")], default="none", required=True, tracking=True,
    )
    clearing_date = fields.Date(tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="bill_id.currency_id", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
         ("released", "Released"), ("rejected", "Rejected"), ("void", "Void")],
        default="draft", required=True, tracking=True,
    )
    payment_id = fields.Many2one("account.payment", readonly=True, copy=False, tracking=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("sedar.finance.disbursement") or "New"
        return super().create(vals_list)

    def write(self, values):
        if values.get("state") in ("approved", "released", "rejected", "void") and not self.env.context.get("sedar_workflow"):
            raise UserError(_("Use the Finance Manager workflow actions to change this state."))
        allowed = {"message_follower_ids", "message_partner_ids"}
        if not self.env.context.get("sedar_posting") and not self.env.context.get("sedar_workflow") and set(values) - allowed and any(
            record.state in ("released", "void") for record in self
        ):
            raise UserError(_("A released or void disbursement is locked."))
        return super().write(values)

    @api.constrains("amount", "payment_type", "check_number", "check_date")
    def _check_values(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Disbursement amount must be greater than zero."))
            if record.payment_type == "check" and (not record.check_number or not record.check_date):
                raise ValidationError(_("Check number and check date are required for check payments."))

    @api.onchange("purchase_id")
    def _onchange_purchase_id(self):
        if self.bill_id and not self._bill_belongs_to_po():
            self.bill_id = False

    @api.onchange("bill_id")
    def _onchange_bill_id(self):
        if self.bill_id:
            self.amount = self.bill_id.amount_residual

    def _bill_belongs_to_po(self):
        self.ensure_one()
        return self.purchase_id in self.bill_id.invoice_line_ids.purchase_line_id.order_id

    def _check_release_requirements(self):
        self.ensure_one()
        if self.purchase_id.state not in ("purchase", "done"):
            raise UserError(_("The purchase order must be approved before any cash or check release."))
        if self.bill_id.state != "posted" or self.bill_id.move_type != "in_invoice" or not self._bill_belongs_to_po():
            raise UserError(_("Select a posted vendor bill created from this purchase order."))
        if self.bill_id.company_id != self.company_id or self.journal_id.company_id != self.company_id:
            raise UserError(_("The purchase, bill, journal, and disbursement must use the same company."))
        if self.amount > self.bill_id.amount_residual:
            raise UserError(_("Disbursement amount cannot exceed the vendor bill residual."))

    def action_submit(self):
        for record in self.filtered(lambda item: item.state in ("draft", "rejected")):
            record._check_release_requirements()
            record.state = "submitted"

    def action_approve(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may approve disbursements."))
        for record in self.filtered(lambda item: item.state == "submitted"):
            record._check_release_requirements()
            record.with_context(sedar_workflow=True).write({"state": "approved", "approved_by_id": self.env.user.id})

    def action_release(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may release disbursements."))
        for record in self.filtered(lambda item: item.state == "approved"):
            record._check_release_requirements()
            register = self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=record.bill_id.ids,
            ).create({"journal_id": record.journal_id.id, "payment_date": record.date, "amount": record.amount})
            payments = register._create_payments()
            payment = payments[:1]
            payment.write({
                "sedar_disbursement_id": record.id, "sedar_purchase_id": record.purchase_id.id,
                "sedar_vessel_id": record.vessel_id.id, "sedar_job_order_id": record.job_order_id.id,
                "sedar_maintenance_request_id": record.maintenance_request_id.id,
                "sedar_check_number": record.check_number,
            })
            record.with_context(sedar_workflow=True).write({
                "payment_id": payment.id, "state": "released",
                "check_status": "outstanding" if record.payment_type == "check" else "none",
            })

    def action_mark_cleared(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_officer"):
            raise UserError(_("Only a Finance Officer or Manager may clear checks."))
        for record in self:
            if record.payment_type != "check" or record.state != "released":
                raise UserError(_("Only a released check can be cleared."))
            record.with_context(sedar_workflow=True).write({
                "check_status": "cleared", "clearing_date": fields.Date.context_today(self),
            })

    def action_mark_stale(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_officer"):
            raise UserError(_("Only a Finance Officer or Manager may mark checks stale."))
        for record in self:
            if record.payment_type != "check" or record.state != "released":
                raise UserError(_("Only a released check can be marked stale."))
            record.with_context(sedar_workflow=True).check_status = "stale"

    def action_void(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may void checks."))
        for record in self:
            if record.payment_type != "check" or record.state != "released" or record.check_status == "cleared":
                raise UserError(_("Only an uncleared released check can be voided."))
            record.payment_id.move_id.line_ids.remove_move_reconcile()
            record.payment_id.action_cancel()
            record.with_context(sedar_posting=True, sedar_workflow=True).write({
                "state": "void", "check_status": "void", "clearing_date": False,
            })

    def action_reject(self):
        if not self.env.user.has_group("sedar_finance_operations.group_finance_manager"):
            raise UserError(_("Only a Finance Manager may reject disbursements."))
        self.filtered(lambda record: record.state == "submitted").with_context(sedar_workflow=True).write({"state": "rejected"})

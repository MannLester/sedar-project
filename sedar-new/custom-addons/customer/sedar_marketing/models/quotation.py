from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarMarketingQuotation(models.Model):
    _name = "sedar.marketing.quotation"
    _description = "SEDAR Marketing Quotation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Quotation", default="New", readonly=True, copy=False, index=True)
    revision_number = fields.Integer(default=1, readonly=True, copy=False)
    original_quotation_id = fields.Many2one(
        "sedar.marketing.quotation", readonly=True, copy=False, ondelete="restrict"
    )
    supersedes_quotation_id = fields.Many2one(
        "sedar.marketing.quotation", readonly=True, copy=False, ondelete="restrict"
    )
    superseded_by_quotation_id = fields.Many2one(
        "sedar.marketing.quotation", readonly=True, copy=False, ondelete="restrict"
    )
    service_order_id = fields.Many2one(
        "sedar.marine.service.order", string="Service Request", required=True,
        index=True, ondelete="restrict", tracking=True
    )
    customer_id = fields.Many2one(
        "res.partner", required=True, index=True, ondelete="restrict", tracking=True
    )
    contact_id = fields.Many2one("res.partner", required=True, ondelete="restrict", tracking=True)
    subject = fields.Char(required=True, tracking=True)
    purchase_order_reference = fields.Char()
    line_ids = fields.One2many("sedar.marketing.quotation.line", "quotation_id", string="Line Items", copy=True)
    amount_untaxed = fields.Monetary(compute="_compute_amounts", store=True)
    tax_amount = fields.Monetary(compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(compute="_compute_amounts", store=True)
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    validity_days = fields.Integer(default=30, required=True)
    valid_until = fields.Date(compute="_compute_valid_until", store=True)
    issued_at = fields.Datetime(readonly=True, copy=False)
    terms_and_conditions = fields.Text()
    internal_notes = fields.Text()
    terms_reference = fields.Char()
    revision_reason = fields.Text(copy=False)
    prepared_by_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, readonly=True
    )
    status = fields.Selection([
        ("draft", "Draft"), ("internal_approval", "For Internal Approval"),
        ("ready", "Ready to Send"), ("sent", "Sent"), ("viewed", "Viewed"),
        ("customer_approved", "Customer Approved"), ("rejected", "Rejected"),
        ("expired", "Expired"), ("superseded", "Superseded"),
    ], default="draft", required=True, tracking=True, index=True, copy=False)
    response_type = fields.Selection([
        ("approved", "Customer Approved"), ("rejected", "Rejected"),
        ("revision", "Requested Revision"),
    ], copy=False)
    response_contact_id = fields.Many2one("res.partner", copy=False, ondelete="restrict")
    response_date = fields.Datetime(copy=False)
    customer_notes = fields.Text(copy=False)
    rejection_reason = fields.Text(copy=False)
    submitted_for_internal_approval_at = fields.Datetime(readonly=True, copy=False)
    sent_at = fields.Datetime(readonly=True, copy=False)
    viewed_at = fields.Datetime(readonly=True, copy=False)
    contract_ids = fields.One2many("sedar.marketing.contract", "quotation_id")

    _name_unique = models.Constraint("UNIQUE(name)", "Quotation number must be unique.")

    @api.depends("line_ids.subtotal", "line_ids.tax_amount")
    def _compute_amounts(self):
        for quotation in self:
            quotation.amount_untaxed = sum(quotation.line_ids.mapped("subtotal"))
            quotation.tax_amount = sum(quotation.line_ids.mapped("tax_amount"))
            quotation.amount_total = quotation.amount_untaxed + quotation.tax_amount

    @api.depends("issued_at", "validity_days")
    def _compute_valid_until(self):
        for quotation in self:
            start = fields.Date.to_date(quotation.issued_at) if quotation.issued_at else False
            quotation.valid_until = start + relativedelta(days=quotation.validity_days) if start else False

    @api.constrains("service_order_id", "customer_id", "contact_id", "validity_days")
    def _check_relationships(self):
        for quotation in self:
            if quotation.service_order_id.client_id.commercial_partner_id != quotation.customer_id.commercial_partner_id:
                raise ValidationError("The quotation customer must match the Service Request customer.")
            if quotation.contact_id.commercial_partner_id != quotation.customer_id.commercial_partner_id:
                raise ValidationError("The quotation contact must belong to the customer.")
            if quotation.validity_days <= 0:
                raise ValidationError("Quotation validity must be greater than zero days.")

    @api.onchange("service_order_id")
    def _onchange_service_order_id(self):
        if self.service_order_id:
            self.customer_id = self.service_order_id.client_id
            self.contact_id = self.service_order_id.contact_id
            self.currency_id = self.service_order_id.currency_id
            self.subject = f"{self.service_order_id.service_type_id.name} for {self.service_order_id.assisted_vessel_name}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("sedar.marketing.quotation") or "New"
        quotations = super().create(vals_list)
        for quotation in quotations:
            if not quotation.original_quotation_id:
                quotation.with_context(sedar_skip_quotation_log=True).write({"original_quotation_id": quotation.id})
            self.env["sedar.marketing.activity"].log(
                quotation.customer_id, "quotations", "created",
                f"Quotation {quotation.name} created.", quotation,
            )
            self.env["sedar.marketing.transaction"].sync_quotation(quotation)
        return quotations

    def write(self, vals):
        before = {item.id: item.status for item in self}
        result = super().write(vals)
        if self.env.context.get("sedar_skip_quotation_log"):
            return result
        for quotation in self:
            if "status" in vals and before[quotation.id] != quotation.status:
                self.env["sedar.marketing.activity"].log(
                    quotation.customer_id, "quotations", "status_changed",
                    f"Quotation {quotation.name} changed status.", quotation,
                    [("status", before[quotation.id], quotation.status)],
                )
            elif vals:
                self.env["sedar.marketing.activity"].log(
                    quotation.customer_id, "quotations", "updated",
                    f"Quotation {quotation.name} updated.", quotation,
                )
            self.env["sedar.marketing.transaction"].sync_quotation(quotation)
        return result

    def action_submit_internal_approval(self):
        self._require_status("draft")
        self.write({"status": "internal_approval", "submitted_for_internal_approval_at": fields.Datetime.now()})

    def action_approve_internal(self):
        self._require_status("internal_approval")
        self.write({"status": "ready"})

    def action_send(self):
        self._require_status("ready")
        self.write({"status": "sent", "issued_at": fields.Datetime.now(), "sent_at": fields.Datetime.now()})
        self.service_order_id.filtered(
            lambda item: item.marketing_status == "quotation_prepared"
        ).action_marketing_send_customer()

    def action_mark_viewed(self):
        self._require_status("sent")
        self.write({"status": "viewed", "viewed_at": fields.Datetime.now()})

    def action_record_customer_approval(self):
        self._require_status("sent", "viewed")
        for quotation in self:
            if not quotation.response_contact_id:
                quotation.response_contact_id = quotation.contact_id
            quotation.write({
                "status": "customer_approved", "response_type": "approved",
                "response_date": fields.Datetime.now(),
            })
            if quotation.service_order_id.marketing_status == "awaiting_customer":
                quotation.service_order_id.action_marketing_approve()

    def action_record_rejection(self):
        self._require_status("sent", "viewed")
        if any(not item.rejection_reason for item in self):
            raise UserError("A rejection reason is required.")
        self.write({"status": "rejected", "response_type": "rejected", "response_date": fields.Datetime.now()})

    def action_create_revision(self):
        self.ensure_one()
        if not self.revision_reason:
            raise UserError("A revision reason is required before creating a new version.")
        revision = self.copy({
            "name": "New", "revision_number": self.revision_number + 1,
            "original_quotation_id": self.original_quotation_id.id,
            "supersedes_quotation_id": self.id, "status": "draft",
            "issued_at": False, "revision_reason": self.revision_reason,
        })
        self.write({"status": "superseded", "superseded_by_quotation_id": revision.id})
        return {
            "type": "ir.actions.act_window", "res_model": self._name, "res_id": revision.id,
            "view_mode": "form", "target": "current",
        }

    def _require_status(self, *allowed):
        if any(item.status not in allowed for item in self):
            raise UserError(f"This action requires quotation status: {', '.join(allowed)}.")


class SedarMarketingQuotationLine(models.Model):
    _name = "sedar.marketing.quotation.line"
    _description = "SEDAR Marketing Quotation Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    quotation_id = fields.Many2one(
        "sedar.marketing.quotation", required=True, ondelete="cascade", index=True
    )
    description = fields.Char(required=True)
    quantity = fields.Float(default=1.0, required=True)
    unit_price = fields.Monetary(required=True)
    tax_rate = fields.Float(string="VAT %", default=12.0)
    currency_id = fields.Many2one(related="quotation_id.currency_id")
    subtotal = fields.Monetary(compute="_compute_amount", store=True)
    tax_amount = fields.Monetary(compute="_compute_amount", store=True)

    @api.depends("quantity", "unit_price", "tax_rate")
    def _compute_amount(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
            line.tax_amount = line.subtotal * line.tax_rate / 100.0

    @api.constrains("quantity", "unit_price", "tax_rate")
    def _check_amounts(self):
        for line in self:
            if line.quantity <= 0 or line.unit_price < 0 or line.tax_rate < 0:
                raise ValidationError("Quotation quantities must be positive and rates cannot be negative.")

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .purchase_bid_common import BID_AUDIT_FIELDS, BID_COMMERCIAL_FIELDS, _check_duplicate_value_pairs


class SedarPurchaseBid(models.Model):
    _name = "sedar.purchase.bid"
    _description = "SEDAR Purchase Bid"
    _inherit = ["mail.thread"]
    _order = "received_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    request_id = fields.Many2one(
        "sedar.purchase.request",
        required=True,
        ondelete="restrict",
        index=True,
        check_company=True,
        tracking=True,
    )
    bidder_id = fields.Many2one(
        "res.partner",
        string="Bidder",
        required=True,
        ondelete="restrict",
        index=True,
        check_company=True,
        domain=[("supplier_rank", ">", 0)],
        tracking=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, index=True, readonly=True
    )
    currency_id = fields.Many2one(
        related="request_id.currency_id", store=True, readonly=True
    )
    state = fields.Selection(
        [("draft", "Draft"), ("received", "Received"), ("withdrawn", "Withdrawn")],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )
    capture_source = fields.Selection(
        [("manual", "Manual Capture"), ("legacy", "Legacy Conversion")],
        default="manual",
        required=True,
        readonly=True,
        copy=False,
    )
    received_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True
    )
    validity_date = fields.Date(tracking=True)
    promised_delivery_date = fields.Date(tracking=True)
    delivery_terms = fields.Text()
    availability_notes = fields.Text()
    payment_terms = fields.Text()
    warranty_notes = fields.Text()
    commercial_notes = fields.Text()
    quotation_file = fields.Binary(attachment=True, copy=False)
    quotation_filename = fields.Char(copy=False)
    line_ids = fields.One2many(
        "sedar.purchase.bid.line", "bid_id", string="Quoted Products", copy=True
    )
    total_amount = fields.Monetary(
        compute="_compute_total_amount", store=True, currency_field="currency_id"
    )
    received_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    received_at = fields.Datetime(readonly=True, copy=False)
    withdrawn_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    withdrawn_at = fields.Datetime(readonly=True, copy=False)
    withdrawal_reason = fields.Text(copy=False)
    award_ids = fields.One2many(
        "sedar.purchase.line.award", "bid_id", readonly=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    quoted_line_count = fields.Integer(
        compute="_compute_workspace_summary", compute_sudo=True, store=True,
    )
    active_request_line_count = fields.Integer(
        compute="_compute_workspace_summary", compute_sudo=True, store=True,
    )
    coverage_state = fields.Selection(
        [("none", "No Coverage"), ("partial", "Partial Coverage"),
         ("full", "Full Coverage")],
        compute="_compute_workspace_summary", compute_sudo=True, store=True,
    )
    award_count = fields.Integer(
        compute="_compute_workspace_summary", compute_sudo=True, store=True,
    )
    awarded_amount = fields.Monetary(
        compute="_compute_workspace_summary", compute_sudo=True, store=True,
        currency_field="currency_id",
    )

    _request_bidder_unique = models.Constraint(
        "UNIQUE(request_id, bidder_id)",
        "Only one Bid per Bidder is allowed for each Purchase Request.",
    )
    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Bid references must be unique.",
    )

    @api.depends("line_ids.subtotal", "currency_id")
    def _compute_total_amount(self):
        for bid in self:
            amount = sum(bid.line_ids.mapped("subtotal"))
            bid.total_amount = bid.currency_id.round(amount) if bid.currency_id else amount

    @api.depends(
        "line_ids.request_line_id.line_state",
        "request_id.line_ids.line_state",
        "award_ids.state",
        "award_ids.quantity",
        "award_ids.unit_price",
        "currency_id",
    )
    def _compute_workspace_summary(self):
        for bid in self:
            active_request_lines = bid.sudo().request_id.line_ids.filtered(
                lambda line: line.line_state == "active"
            )
            quoted_lines = bid.sudo().line_ids.filtered(
                lambda line: line.request_line_id in active_request_lines
            )
            active_awards = bid.sudo().award_ids.filtered(
                lambda award: award.state in {"awarded", "ordered"}
            )
            bid.active_request_line_count = len(active_request_lines)
            bid.quoted_line_count = len(quoted_lines)
            if not quoted_lines:
                bid.coverage_state = "none"
            elif len(quoted_lines) < len(active_request_lines):
                bid.coverage_state = "partial"
            else:
                bid.coverage_state = "full"
            bid.award_count = len(active_awards)
            amount = sum(
                award.quantity * award.unit_price for award in active_awards
            )
            bid.awarded_amount = (
                bid.currency_id.round(amount) if bid.currency_id else amount
            )

    def _check_bid_officer(self):
        for bid in self:
            if self.env.user != bid.request_id._get_valid_officer():
                raise AccessError(_(
                    "Only the configured Procurement and Inventory Officer may maintain Bids."
                ))

    @api.constrains("request_id", "bidder_id")
    def _check_request_and_bidder(self):
        for bid in self:
            if bid.request_id.state != "approved":
                raise ValidationError(_(
                    "Bids may be recorded only for an approved Purchase Request."
                ))
            bidder = bid.bidder_id
            if bidder != bidder.commercial_partner_id:
                raise ValidationError(_(
                    "Select the Bidder's canonical commercial partner, not an individual contact."
                ))
            if bidder.supplier_rank <= 0:
                raise ValidationError(_("The Bidder must be an eligible supplier."))
            if bidder.company_id and bidder.company_id != bid.company_id:
                raise ValidationError(_(
                    "The Bidder must be shared or belong to the Purchase Request company."
                ))

    @api.constrains("received_date", "validity_date", "promised_delivery_date")
    def _check_commercial_dates(self):
        for bid in self:
            if bid.validity_date and bid.validity_date < bid.received_date:
                raise ValidationError(_(
                    "Bid validity cannot end before the quotation was received."
                ))
            if (
                bid.promised_delivery_date
                and bid.promised_delivery_date < bid.received_date
            ):
                raise ValidationError(_(
                    "Promised delivery cannot be before the quotation was received."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        _check_duplicate_value_pairs(
            self,
            vals_list,
            "request_id",
            "bidder_id",
            _("Only one Bid per Bidder is allowed for each Purchase Request."),
        )
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            request = self.env["sedar.purchase.request"].browse(vals.get("request_id"))
            if not self.env.su:
                if not request or self.env.user != request._get_valid_officer():
                    raise AccessError(_(
                        "Only the configured Procurement and Inventory Officer may record Bids."
                    ))
                if BID_AUDIT_FIELDS.intersection(vals):
                    if vals.get("state") not in (None, False, "draft") or vals.get(
                        "capture_source"
                    ) not in (None, False, "manual"):
                        raise AccessError(_(
                            "Bid state, source, and audit fields are controlled by workflow actions."
                        ))
                    if (BID_AUDIT_FIELDS - {"state", "capture_source"}).intersection(vals):
                        raise AccessError(_(
                            "Bid state, source, and audit fields are controlled by workflow actions."
                        ))
            if vals.get("name") not in (None, False, "New") and not self.env.su:
                raise AccessError(_("Bid references are assigned automatically."))
            if vals.get("name") in (None, False, "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sedar.purchase.bid"
                ) or "New"
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if not self.env.su:
            self._check_bid_officer()
            if "name" in vals:
                raise AccessError(_(
                    "Bid references are assigned automatically and immutable."
                ))
            if {"request_id", "bidder_id"}.intersection(vals):
                raise AccessError(_(
                    "A Bid cannot be reassigned to another Purchase Request or Bidder."
                ))
            if BID_AUDIT_FIELDS.intersection(vals):
                raise AccessError(_(
                    "Bid state, source, and audit fields are controlled by workflow actions."
                ))
            if self.filtered(lambda bid: bid.state != "draft") and BID_COMMERCIAL_FIELDS.intersection(vals):
                raise AccessError(_(
                    "Received and withdrawn Bids are immutable procurement history."
                ))
            if "withdrawal_reason" in vals and self.filtered(
                lambda bid: bid.state == "withdrawn"
            ):
                raise AccessError(_("A withdrawn Bid's reason is immutable."))
            if vals.get("request_id"):
                request = self.env["sedar.purchase.request"].browse(vals["request_id"])
                if self.env.user != request._get_valid_officer():
                    raise AccessError(_(
                        "Only the configured Procurement and Inventory Officer may move a Bid to that request."
                    ))
        return super().write(vals)

    def _validate_for_receipt(self):
        for bid in self:
            if not bid.line_ids:
                raise UserError(_("Add at least one quoted product before receiving the Bid."))
            if bid.capture_source == "manual" and not bid.quotation_file:
                raise UserError(_(
                    "Attach the supplier quotation before marking the Bid received."
                ))
            bid.line_ids._validate_bid_line_contract()

    def action_receive(self):
        self._check_bid_officer()
        for bid in self:
            self.env.cr.execute(
                "SELECT id FROM sedar_purchase_bid WHERE id = %s FOR UPDATE", [bid.id]
            )
            bid.invalidate_recordset()
            if bid.state != "draft":
                raise UserError(_("Only a draft Bid can be marked received."))
            bid._validate_for_receipt()
            super(SedarPurchaseBid, bid.sudo()).write({
                "state": "received",
                "received_by_id": self.env.user.id,
                "received_at": fields.Datetime.now(),
            })
        return True

    def action_withdraw(self):
        self._check_bid_officer()
        for bid in self:
            self.env.cr.execute(
                "SELECT id FROM sedar_purchase_bid WHERE id = %s FOR UPDATE", [bid.id]
            )
            bid.invalidate_recordset()
            if bid.state != "received":
                raise UserError(_("Only a received Bid can be withdrawn."))
            if bid.sudo().award_ids:
                raise UserError(_(
                    "A Bid with Line Award history cannot be withdrawn."
                ))
            if not bid.withdrawal_reason:
                raise UserError(_("Enter a withdrawal reason before withdrawing the Bid."))
            super(SedarPurchaseBid, bid.sudo()).write({
                "state": "withdrawn",
                "withdrawn_by_id": self.env.user.id,
                "withdrawn_at": fields.Datetime.now(),
            })
        return True

    def unlink(self):
        if not self.env.su:
            self._check_bid_officer()
            if self.filtered(lambda bid: bid.state != "draft"):
                raise AccessError(_(
                    "Received and withdrawn Bids cannot be deleted. Withdraw received offers to preserve history."
                ))
        return super().unlink()

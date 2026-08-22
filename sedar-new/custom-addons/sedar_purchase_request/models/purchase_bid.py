from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


BID_AUDIT_FIELDS = {
    "state",
    "capture_source",
    "received_by_id",
    "received_at",
    "withdrawn_by_id",
    "withdrawn_at",
}
BID_COMMERCIAL_FIELDS = {
    "request_id",
    "bidder_id",
    "received_date",
    "validity_date",
    "promised_delivery_date",
    "delivery_terms",
    "availability_notes",
    "payment_terms",
    "warranty_notes",
    "commercial_notes",
    "quotation_file",
    "quotation_filename",
    "line_ids",
}


def _check_duplicate_value_pairs(
    model, vals_list, first_field, second_field, error_message
):
    seen = set()
    for vals in vals_list:
        key = (vals.get(first_field), vals.get(second_field))
        if not all(key):
            continue
        duplicate = key in seen or model.sudo().search_count([
            (first_field, "=", key[0]),
            (second_field, "=", key[1]),
        ])
        if duplicate:
            raise ValidationError(error_message)
        seen.add(key)


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


class SedarPurchaseBidLine(models.Model):
    _name = "sedar.purchase.bid.line"
    _description = "SEDAR Purchase Bid Line"
    _rec_name = "award_display_name"
    _order = "bid_id, request_line_id"
    _check_company_auto = True

    bid_id = fields.Many2one(
        "sedar.purchase.bid", required=True, ondelete="cascade", index=True, check_company=True
    )
    request_id = fields.Many2one(
        related="bid_id.request_id", store=True, index=True, readonly=True
    )
    request_line_id = fields.Many2one(
        "sedar.purchase.request.line",
        required=True,
        ondelete="restrict",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="bid_id.company_id", store=True, index=True, readonly=True
    )
    currency_id = fields.Many2one(
        related="bid_id.currency_id", store=True, readonly=True
    )
    product_id = fields.Many2one(
        related="request_line_id.product_id", store=True, readonly=True
    )
    product_uom_id = fields.Many2one(
        related="request_line_id.product_uom_id", store=True, readonly=True
    )
    quantity = fields.Float(required=True, readonly=True, aggregator=False)
    unit_price = fields.Float(
        required=True, digits=(16, 6), default=0.0, aggregator=False,
    )
    subtotal = fields.Monetary(
        compute="_compute_subtotal", store=True, currency_field="currency_id",
        aggregator=False,
    )
    availability_note = fields.Char()
    promised_delivery_date = fields.Date()
    delivery_terms = fields.Text()
    notes = fields.Text()
    bidder_id = fields.Many2one(
        related="bid_id.bidder_id", store=True, readonly=True,
    )
    validity_date = fields.Date(related="bid_id.validity_date", store=True, readonly=True)
    warranty_notes = fields.Text(related="bid_id.warranty_notes", readonly=True)
    award_display_name = fields.Char(compute="_compute_award_display_name")

    _bid_request_line_unique = models.Constraint(
        "UNIQUE(bid_id, request_line_id)",
        "A Purchase Request line can appear only once in the same Bid.",
    )

    @api.depends("quantity", "unit_price", "currency_id")
    def _compute_subtotal(self):
        for line in self:
            amount = line.quantity * line.unit_price
            line.subtotal = line.currency_id.round(amount) if line.currency_id else amount

    @api.depends(
        "bidder_id", "unit_price", "currency_id", "validity_date",
        "promised_delivery_date",
    )
    def _compute_award_display_name(self):
        for line in self:
            price = _(
                "%(currency)s %(price)s",
                currency=line.currency_id.name or "",
                price=f"{line.unit_price:.6f}",
            )
            validity = line.validity_date or _("No expiry")
            delivery = line.promised_delivery_date or line.bid_id.promised_delivery_date or _("No promise")
            line.award_display_name = _(
                "%(bidder)s — %(price)s — Valid %(validity)s — Delivery %(delivery)s",
                bidder=line.bidder_id.display_name,
                price=price,
                validity=validity,
                delivery=delivery,
            )

    @api.constrains(
        "bid_id", "request_line_id", "quantity", "unit_price", "promised_delivery_date"
    )
    def _check_bid_line_contract(self):
        self._validate_bid_line_contract()

    def _validate_bid_line_contract(self):
        for line in self:
            if line.request_line_id.request_id != line.bid_id.request_id:
                raise ValidationError(_(
                    "A Bid cannot quote a line from another Purchase Request."
                ))
            rounding = line.request_line_id.product_uom_id.rounding
            if float_compare(
                line.quantity,
                line.request_line_id.quantity,
                precision_rounding=rounding,
            ) != 0:
                raise ValidationError(_(
                    "A Bid line must quote the full requested quantity."
                ))
            if line.unit_price < 0:
                raise ValidationError(_("Bid unit price cannot be negative."))
            if (
                line.promised_delivery_date
                and line.promised_delivery_date < line.bid_id.received_date
            ):
                raise ValidationError(_(
                    "A line's promised delivery cannot be before the Bid was received."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        _check_duplicate_value_pairs(
            self,
            vals_list,
            "bid_id",
            "request_line_id",
            _("A Purchase Request line can appear only once in the same Bid."),
        )
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            bid = self.env["sedar.purchase.bid"].browse(vals.get("bid_id"))
            request_line = self.env["sedar.purchase.request.line"].browse(
                vals.get("request_line_id")
            )
            if not self.env.su:
                bid._check_bid_officer()
                if bid.state != "draft":
                    raise AccessError(_("Bid lines are editable only while the Bid is draft."))
            if request_line:
                vals["quantity"] = request_line.quantity
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if not self.env.su:
            bids = self.mapped("bid_id")
            if vals.get("bid_id"):
                bids |= self.env["sedar.purchase.bid"].browse(vals["bid_id"])
            bids._check_bid_officer()
            if bids.filtered(lambda bid: bid.state != "draft"):
                raise AccessError(_("Bid lines are editable only while the Bid is draft."))
            if {"bid_id", "request_line_id", "quantity"}.intersection(vals):
                raise AccessError(_(
                    "Bid, Purchase Request line, and quantity snapshots cannot be reassigned."
                ))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            bids = self.mapped("bid_id")
            bids._check_bid_officer()
            if bids.filtered(lambda bid: bid.state != "draft"):
                raise AccessError(_(
                    "Received and withdrawn Bid lines cannot be deleted."
                ))
        return super().unlink()

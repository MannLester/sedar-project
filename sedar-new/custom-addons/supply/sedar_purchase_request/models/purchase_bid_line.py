from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare
from .purchase_bid_common import _check_duplicate_value_pairs


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

from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero
from .purchase_award_common import AWARD_INTERNAL_CONTEXT, GENERATED_LINE_FACT_FIELDS, GENERATED_ORDER_FACT_FIELDS, PO_LINE_SOURCE_FIELDS, _company_business_date


class SedarPurchaseRequestLineAward(models.Model):
    _inherit = "sedar.purchase.request.line"

    line_state = fields.Selection(
        [("active", "Active"), ("cancelled", "Cancelled")],
        default="active", required=True, readonly=True, index=True,
    )
    current_award_id = fields.Many2one(
        "sedar.purchase.line.award", readonly=True, copy=False, ondelete="restrict",
        check_company=True, groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    award_history_ids = fields.One2many(
        "sedar.purchase.line.award", "request_line_id", readonly=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    cancellation_reason = fields.Text(readonly=True, copy=False)
    cancelled_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    cancelled_at = fields.Datetime(readonly=True, copy=False)

    def write(self, vals):
        controlled = {"line_state", "current_award_id", "cancellation_reason", "cancelled_by_id", "cancelled_at"}
        if controlled.intersection(vals) and (
            not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
        ):
            raise AccessError(_("Line Award and cancellation fields change only through controlled actions."))
        return super().write(vals)

    def action_open_award_wizard(self):
        self.ensure_one()
        self.request_id._check_procurement_inventory_officer()
        if self.line_state != "active" or self.current_award_id:
            raise UserError(_("This Purchase Request line cannot receive another active award."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Award Product Line"),
            "res_model": "sedar.purchase.line.award.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_line_id": self.id},
        }

    def action_open_cancel_wizard(self):
        self.ensure_one()
        self.request_id._check_procurement_inventory_officer()
        if (
            self.line_state != "active"
            or self.current_award_id
            or self.sudo().award_history_ids
        ):
            raise UserError(_(
                "Only an active line with no Line Award history can be cancelled."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Cancel Purchase Request Line"),
            "res_model": "sedar.purchase.request.line.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_line_id": self.id},
        }

    def _validate_award_source(self, bid_line):
        request = self.request_id
        if request.state != "approved":
            raise UserError(_("Line Awards require an approved Purchase Request."))
        if self.line_state != "active" or self.current_award_id:
            raise UserError(_("This Purchase Request line already has an award or is cancelled."))
        if bid_line.request_line_id != self or bid_line.bid_id.request_id != request:
            raise ValidationError(_("Select a Bid line for this Purchase Request product."))
        bid = bid_line.bid_id
        if bid.state != "received":
            raise UserError(_("Only a Received Bid can win a Line Award."))
        if bid.company_id != request.company_id or bid.currency_id != request.currency_id:
            raise ValidationError(_("The winning Bid must use the Purchase Request company and currency."))
        if bid_line.product_id != self.product_id or bid_line.product_uom_id != self.product_uom_id:
            raise ValidationError(_("The winning Bid line must match the requested product and unit."))
        if float_compare(
            bid_line.quantity, self.quantity, precision_rounding=self.product_uom_id.rounding
        ) != 0:
            raise ValidationError(_("The winning Bid must quote the full requested quantity."))
        return bid

    def _validate_award_exceptions(self, bid, bid_line, reason, expired_override,
                                   expired_override_reason, zero_price_confirmed):
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Enter a best-value reason for the Line Award."))
        expired = bool(bid.validity_date and bid.validity_date < _company_business_date(self.request_id))
        override_reason = (expired_override_reason or "").strip()
        if expired and (not expired_override or not override_reason):
            raise UserError(_("An expired Bid requires an explicit override and reason."))
        if not expired and (expired_override or override_reason):
            raise UserError(_("An expiry override is allowed only when the Bid is expired."))
        zero_price = float_is_zero(bid_line.unit_price, precision_digits=6)
        if zero_price and not zero_price_confirmed:
            raise UserError(_("Confirm explicitly that the supplier quoted a zero unit price."))
        return reason, expired, override_reason, zero_price

    def _create_line_award(self, bid_line, reason, expired_override=False,
                           expired_override_reason=None, zero_price_confirmed=False):
        self.ensure_one()
        request = self.request_id
        request._check_procurement_inventory_officer()
        self.env.cr.execute(
            "SELECT id FROM sedar_purchase_request_line WHERE id = %s FOR UPDATE", [self.id]
        )
        self.invalidate_recordset()
        bid = self._validate_award_source(bid_line)
        reason, expired, override_reason, zero_price = self._validate_award_exceptions(
            bid, bid_line, reason, expired_override, expired_override_reason,
            zero_price_confirmed,
        )
        award = self.env["sedar.purchase.line.award"].sudo().with_context(
            **{AWARD_INTERNAL_CONTEXT: True}
        ).create({
            "request_id": request.id,
            "request_line_id": self.id,
            "active_request_line_id": self.id,
            "bid_id": bid.id,
            "bid_line_id": bid_line.id,
            "bidder_id": bid.bidder_id.id,
            "company_id": request.company_id.id,
            "currency_id": request.currency_id.id,
            "product_id": self.product_id.id,
            "product_uom_id": self.product_uom_id.id,
            "quantity": self.quantity,
            "unit_price": bid_line.unit_price,
            "award_reason": reason,
            "awarded_by_id": self.env.user.id,
            "awarded_at": fields.Datetime.now(),
            "expired_bid_override": expired,
            "expired_bid_override_reason": override_reason if expired else False,
            "zero_price_confirmed": bool(zero_price and zero_price_confirmed),
        })
        self.sudo().with_context(**{AWARD_INTERNAL_CONTEXT: True}).write({
            "current_award_id": award.id,
        })
        request.message_post(body=Markup("<p>%s</p>") % escape(_(
            "A Line Award was recorded for %(product)s. Commercial details remain in the restricted Awards tab.",
            product=self.product_id.display_name,
        )))
        return award

    def _cancel_for_procurement(self, reason):
        self.ensure_one()
        request = self.request_id
        request._check_procurement_inventory_officer()
        self.env.cr.execute(
            "SELECT id FROM sedar_purchase_request_line WHERE id = %s FOR UPDATE", [self.id]
        )
        self.invalidate_recordset()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Enter a reason for cancelling the requested product."))
        if (
            request.state != "approved"
            or self.line_state != "active"
            or self.current_award_id
            or self.sudo().award_history_ids
        ):
            raise UserError(_(
                "Only an active line with no Line Award history on an approved request can be cancelled."
            ))
        if self.env["purchase.order.line"].sudo().search_count([
            ("sedar_purchase_request_line_id", "=", self.id),
        ]):
            raise UserError(_("A line already handed to a Purchase Order cannot be cancelled."))
        self.sudo().with_context(**{AWARD_INTERNAL_CONTEXT: True}).write({
            "line_state": "cancelled",
            "cancellation_reason": reason,
            "cancelled_by_id": self.env.user.id,
            "cancelled_at": fields.Datetime.now(),
        })
        if not request.line_ids.filtered(lambda line: line.line_state == "active"):
            request.sudo().write({"state": "cancelled"})
        request.message_post(body=Markup("<p>%s</p>") % escape(_(
            "Cancelled requested product %(product)s: %(reason)s",
            product=self.product_id.display_name,
            reason=reason,
        )))
        return True


class PurchaseOrderAward(models.Model):
    _inherit = "purchase.order"

    sedar_bid_id = fields.Many2one(
        "sedar.purchase.bid", string="Winning Bid", readonly=True, copy=False,
        index=True, ondelete="restrict", check_company=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )

    _sedar_request_bid_unique = models.Constraint(
        "UNIQUE(sedar_purchase_request_id, sedar_bid_id)",
        "Only one Purchase Order may be created for a winning Bid in a Purchase Request.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("sedar_bid_id") for vals in vals_list) and (
            not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
        ):
            raise AccessError(_("Procurement source links are set only by grouped Purchase Order creation."))
        return super().create(vals_list)

    def write(self, vals):
        protected = "sedar_bid_id" in vals or (
            "sedar_purchase_request_id" in vals and self.filtered("sedar_bid_id")
        )
        protected_generated_facts = GENERATED_ORDER_FACT_FIELDS.intersection(vals) and self.filtered("sedar_bid_id")
        if (protected or protected_generated_facts) and (
            not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
        ):
            raise AccessError(_("Procurement source links are immutable."))
        return super().write(vals)

    def unlink(self):
        if self.filtered("sedar_bid_id"):
            raise UserError(_("A generated procurement order cannot be deleted; cancel it to preserve award history."))
        return super().unlink()


class PurchaseOrderLineAward(models.Model):
    _inherit = "purchase.order.line"

    sedar_purchase_request_line_id = fields.Many2one(
        "sedar.purchase.request.line", readonly=True, copy=False, index=True,
        ondelete="restrict", check_company=True,
    )
    sedar_bid_line_id = fields.Many2one(
        "sedar.purchase.bid.line", readonly=True, copy=False, index=True,
        ondelete="restrict", check_company=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    sedar_line_award_id = fields.Many2one(
        "sedar.purchase.line.award", readonly=True, copy=False, index=True,
        ondelete="restrict", check_company=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )

    _sedar_award_po_line_unique = models.Constraint(
        "UNIQUE(sedar_line_award_id)",
        "A Line Award can appear on only one Purchase Order line.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(PO_LINE_SOURCE_FIELDS.intersection(vals) for vals in vals_list) and (
            not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
        ):
            raise AccessError(_("Procurement line source links are set only by grouped Purchase Order creation."))
        return super().create(vals_list)

    def write(self, vals):
        protected = PO_LINE_SOURCE_FIELDS.intersection(vals)
        protected_generated_facts = GENERATED_LINE_FACT_FIELDS.intersection(vals) and self.filtered("sedar_line_award_id")
        if (protected or protected_generated_facts) and (
            not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
        ):
            raise AccessError(_("Procurement line source links are immutable."))
        return super().write(vals)

    def unlink(self):
        if self.filtered("sedar_line_award_id"):
            raise UserError(_("A Purchase Order line created from a Line Award cannot be deleted."))
        return super().unlink()


class SedarPurchaseLineAwardWizard(models.TransientModel):
    _name = "sedar.purchase.line.award.wizard"
    _description = "Award Purchase Request Line"

    request_line_id = fields.Many2one("sedar.purchase.request.line", required=True, readonly=True)
    bid_line_id = fields.Many2one("sedar.purchase.bid.line", required=True)
    bidder_id = fields.Many2one(related="bid_line_id.bidder_id", readonly=True)
    quantity = fields.Float(related="bid_line_id.quantity", readonly=True)
    product_uom_id = fields.Many2one(related="bid_line_id.product_uom_id", readonly=True)
    unit_price = fields.Float(related="bid_line_id.unit_price", readonly=True, digits=(16, 6))
    currency_id = fields.Many2one(related="bid_line_id.currency_id", readonly=True)
    validity_date = fields.Date(related="bid_line_id.validity_date", readonly=True)
    promised_delivery_date = fields.Date(
        related="bid_line_id.promised_delivery_date", readonly=True,
    )
    availability_note = fields.Char(related="bid_line_id.availability_note", readonly=True)
    warranty_notes = fields.Text(related="bid_line_id.warranty_notes", readonly=True)
    award_reason = fields.Text(required=True)
    expired_bid_override = fields.Boolean(string="Approve Expired Bid Override")
    expired_bid_override_reason = fields.Text()
    zero_price_confirmed = fields.Boolean(string="Confirm Zero Unit Price")

    def action_confirm(self):
        self.ensure_one()
        self.request_line_id._create_line_award(
            self.bid_line_id,
            self.award_reason,
            self.expired_bid_override,
            self.expired_bid_override_reason,
            self.zero_price_confirmed,
        )
        return {"type": "ir.actions.act_window_close"}


class SedarPurchaseLineAwardResetWizard(models.TransientModel):
    _name = "sedar.purchase.line.award.reset.wizard"
    _description = "Reset Purchase Line Award"

    award_id = fields.Many2one("sedar.purchase.line.award", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.award_id._reset_with_reason(self.reason)
        return {"type": "ir.actions.act_window_close"}


class SedarPurchaseRequestLineCancelWizard(models.TransientModel):
    _name = "sedar.purchase.request.line.cancel.wizard"
    _description = "Cancel Purchase Request Line"

    request_line_id = fields.Many2one("sedar.purchase.request.line", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.request_line_id._cancel_for_procurement(self.reason)
        return {"type": "ir.actions.act_window_close"}


class SedarPurchaseRequestRecoveryWizard(models.TransientModel):
    _name = "sedar.purchase.request.recovery.wizard"
    _description = "Recover Legacy Purchase Order Handoff"

    request_id = fields.Many2one("sedar.purchase.request", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.request_id._recover_legacy_handoff(self.reason)
        return {"type": "ir.actions.act_window_close"}

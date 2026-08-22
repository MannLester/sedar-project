from collections import defaultdict
from datetime import datetime, time

import pytz
from markupsafe import Markup, escape

from odoo import _, Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


AWARD_INTERNAL_CONTEXT = "sedar_award_workflow"
AWARD_MUTABLE_FIELDS = {"active_request_line_id", "state", "reset_reason", "reset_by_id", "reset_at", "purchase_order_line_id"}
PO_LINE_SOURCE_FIELDS = {
    "sedar_purchase_request_line_id", "sedar_bid_line_id", "sedar_line_award_id",
}
GENERATED_ORDER_FACT_FIELDS = {"partner_id", "company_id", "currency_id"}
GENERATED_LINE_FACT_FIELDS = {
    "order_id", "product_id", "product_uom_id", "product_qty", "price_unit",
    "discount", "technical_price_unit",
}
RECOVERY_AUDIT_FIELDS = {
    "handoff_recovery_reason", "handoff_recovered_by_id", "handoff_recovered_at",
}


def _company_business_date(record):
    company = record.company_id
    timezone = company.partner_id.tz or company.sedar_procurement_inventory_officer_id.tz or "UTC"
    return fields.Date.context_today(record.with_context(tz=timezone))


def _company_midnight_utc(company, date_value):
    timezone = company.partner_id.tz or company.sedar_procurement_inventory_officer_id.tz or "UTC"
    localized = pytz.timezone(timezone).localize(datetime.combine(date_value, time.min))
    return localized.astimezone(pytz.UTC).replace(tzinfo=None)


class SedarPurchaseLineAward(models.Model):
    _name = "sedar.purchase.line.award"
    _description = "SEDAR Purchase Line Award"
    _rec_name = "product_id"
    _order = "awarded_at desc, id desc"
    _check_company_auto = True

    request_id = fields.Many2one(
        "sedar.purchase.request", required=True, readonly=True, ondelete="restrict",
        index=True, check_company=True,
    )
    request_line_id = fields.Many2one(
        "sedar.purchase.request.line", required=True, readonly=True, ondelete="restrict",
        index=True, check_company=True,
    )
    active_request_line_id = fields.Many2one(
        "sedar.purchase.request.line", readonly=True, ondelete="restrict", index=True,
        check_company=True,
    )
    bid_id = fields.Many2one(
        "sedar.purchase.bid", required=True, readonly=True, ondelete="restrict",
        index=True, check_company=True,
    )
    bid_line_id = fields.Many2one(
        "sedar.purchase.bid.line", required=True, readonly=True, ondelete="restrict",
        index=True, check_company=True,
    )
    bidder_id = fields.Many2one("res.partner", required=True, readonly=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True)
    product_id = fields.Many2one("product.product", required=True, readonly=True, ondelete="restrict")
    product_uom_id = fields.Many2one("uom.uom", required=True, readonly=True, ondelete="restrict")
    quantity = fields.Float(required=True, readonly=True)
    unit_price = fields.Float(required=True, readonly=True, digits=(16, 6))
    award_reason = fields.Text(required=True, readonly=True)
    awarded_by_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    awarded_at = fields.Datetime(required=True, readonly=True)
    expired_bid_override = fields.Boolean(readonly=True)
    expired_bid_override_reason = fields.Text(readonly=True)
    zero_price_confirmed = fields.Boolean(readonly=True)
    state = fields.Selection(
        [("awarded", "Awarded"), ("reset", "Reset"), ("ordered", "Ordered")],
        required=True, readonly=True, default="awarded", index=True,
    )
    reset_reason = fields.Text(readonly=True)
    reset_by_id = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    reset_at = fields.Datetime(readonly=True)
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line", readonly=True, ondelete="restrict", index=True,
    )

    _one_active_award_per_line = models.Constraint(
        "UNIQUE(active_request_line_id)",
        "A Purchase Request line can have only one active Line Award.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT):
            raise AccessError(_("Line Awards are created only by the controlled award action."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            not self.env.su
            or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
            or not set(vals) <= AWARD_MUTABLE_FIELDS
        ):
            raise AccessError(_("Line Award facts are immutable and change only through controlled actions."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Line Award history cannot be deleted."))

    def action_open_reset_wizard(self):
        self.ensure_one()
        self.request_id._check_procurement_inventory_officer()
        if self.state != "awarded" or self.purchase_order_line_id:
            raise UserError(_("Only an unordered active Line Award can be reset."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reset Line Award"),
            "res_model": "sedar.purchase.line.award.reset.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_award_id": self.id},
        }

    def _reset_with_reason(self, reason):
        self.ensure_one()
        self.request_id._check_procurement_inventory_officer()
        self.env.cr.execute(
            "SELECT id FROM sedar_purchase_line_award WHERE id = %s FOR UPDATE", [self.id]
        )
        self.invalidate_recordset()
        if self.state != "awarded" or self.purchase_order_line_id:
            raise UserError(_("A Line Award cannot be reset after Purchase Order handoff."))
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Enter a reason for resetting the Line Award."))
        line = self.request_line_id
        award = self.sudo().with_context(**{AWARD_INTERNAL_CONTEXT: True})
        super(SedarPurchaseLineAward, award).write({
            "active_request_line_id": False,
            "state": "reset",
            "reset_reason": reason,
            "reset_by_id": self.env.user.id,
            "reset_at": fields.Datetime.now(),
        })
        award.flush_recordset(["active_request_line_id", "state"])
        line.sudo().with_context(**{AWARD_INTERNAL_CONTEXT: True}).write({"current_award_id": False})
        self.request_id.message_post(body=Markup("<p>%s</p>") % escape(_(
            "The Line Award for %(product)s was reset. Audit details remain in the restricted Awards tab.",
            product=line.product_id.display_name,
        )))
        return True

    def _validate_handoff_integrity(self):
        for award in self:
            line = award.request_line_id
            if (
                award.request_id != line.request_id
                or line.current_award_id != award
                or award.active_request_line_id != line
                or award.bid_line_id.request_line_id != line
                or award.bid_id != award.bid_line_id.bid_id
                or award.bid_id.state != "received"
                or award.bid_id.request_id != award.request_id
                or award.company_id != award.request_id.company_id
                or award.currency_id != award.request_id.currency_id
                or award.product_id != line.product_id
                or award.product_uom_id != line.product_uom_id
                or float_compare(
                    award.quantity,
                    line.quantity,
                    precision_rounding=line.product_uom_id.rounding,
                ) != 0
            ):
                raise ValidationError(_(
                    "A Line Award no longer matches its Purchase Request and Bid source facts."
                ))
            if award.state == "ordered" and not award.purchase_order_line_id:
                raise UserError(_("An ordered Line Award has an incomplete Purchase Order link."))
            if award.state == "awarded" and award.purchase_order_line_id:
                raise UserError(_("A Line Award has an inconsistent Purchase Order state."))


class SedarPurchaseRequestAward(models.Model):
    _inherit = "sedar.purchase.request"

    award_ids = fields.One2many(
        "sedar.purchase.line.award", "request_id", string="Line Awards", readonly=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    award_count = fields.Integer(
        compute="_compute_award_count", compute_sudo=True,
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    handoff_recovery_reason = fields.Text(readonly=True, copy=False)
    handoff_recovered_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    handoff_recovered_at = fields.Datetime(readonly=True, copy=False)
    legacy_handoff_recovery_required = fields.Boolean(
        compute="_compute_legacy_handoff_recovery_required", compute_sudo=True,
    )

    def write(self, vals):
        if RECOVERY_AUDIT_FIELDS.intersection(vals) and (
            not self.env.su or not self.env.context.get(AWARD_INTERNAL_CONTEXT)
        ):
            raise AccessError(_("Legacy handoff recovery audit fields change only through the controlled action."))
        return super().write(vals)

    @api.depends("award_ids")
    def _compute_award_count(self):
        for request in self:
            request.award_count = len(request.sudo().award_ids)

    @api.depends("state", "purchase_order_id", "purchase_order_ids")
    def _compute_legacy_handoff_recovery_required(self):
        for request in self:
            request.legacy_handoff_recovery_required = bool(
                request.state == "po_created"
                and not request.sudo().purchase_order_id
                and not request.sudo().purchase_order_ids
            )

    def action_open_awards(self):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Line Awards"),
            "res_model": "sedar.purchase.line.award",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
        }

    def action_open_bid_comparison(self):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bid Comparison"),
            "res_model": "sedar.purchase.bid.line",
            "view_mode": "list,form",
            "search_view_id": self.env.ref(
                "sedar_purchase_request.view_sedar_purchase_bid_line_search"
            ).id,
            "domain": [
                ("request_id", "=", self.id),
                ("bid_id.state", "=", "received"),
            ],
            "context": {"search_default_group_request_line": 1},
        }

    def action_open_handoff_recovery_wizard(self):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        if not self.legacy_handoff_recovery_required:
            raise UserError(_("This Purchase Request does not require legacy handoff recovery."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Recover Legacy Handoff"),
            "res_model": "sedar.purchase.request.recovery.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _recover_legacy_handoff(self, reason):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        self.env.cr.execute(
            "SELECT id FROM sedar_purchase_request WHERE id = %s FOR UPDATE", [self.id]
        )
        self.invalidate_recordset()
        if not self.legacy_handoff_recovery_required:
            raise UserError(_("This Purchase Request no longer requires legacy handoff recovery."))
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Enter a reason for recovering the legacy handoff."))
        self.sudo().with_context(**{AWARD_INTERNAL_CONTEXT: True}).write({
            "state": "approved",
            "handoff_recovery_reason": reason,
            "handoff_recovered_by_id": self.env.user.id,
            "handoff_recovered_at": fields.Datetime.now(),
        })
        self.message_post(body=Markup("<p>%s</p>") % escape(_(
            "Legacy Purchase Order handoff was returned to procurement review: %(reason)s",
            reason=reason,
        )))
        return True

    def _validate_awards_for_handoff(self):
        self.ensure_one()
        if self.state not in {"approved", "po_created"}:
            raise UserError(_("Only an approved Purchase Request can create Purchase Orders."))
        if self.legacy_handoff_recovery_required:
            raise UserError(_("Recover the incomplete legacy handoff before creating Purchase Orders."))
        active_lines = self.line_ids.filtered(lambda line: line.line_state == "active")
        if not active_lines:
            raise UserError(_("There are no active Purchase Request lines to order."))
        missing = active_lines.filtered(lambda line: not line.current_award_id)
        if missing:
            raise UserError(_("Award every active Purchase Request line before creating Purchase Orders."))
        invalid = active_lines.filtered(
            lambda line: line.current_award_id.state not in {"awarded", "ordered"}
        )
        if invalid:
            raise UserError(_("Every active line must have a valid Line Award."))
        active_lines.mapped("current_award_id")._validate_handoff_integrity()
        return active_lines

    def _mapped_supplier_taxes(self, award, fiscal_position):
        taxes = award.product_id.supplier_taxes_id._filter_taxes_by_company(self.company_id)
        if taxes.filtered("price_include"):
            raise UserError(_(
                "Product %(product)s uses a price-included supplier tax. Configure tax-exclusive supplier taxes before creating Purchase Orders.",
                product=award.product_id.display_name,
            ))
        return fiscal_position.map_tax(taxes)

    def _purchase_order_notes(self, bid):
        sections = [
            (_("Delivery terms"), bid.delivery_terms),
            (_("Payment terms quoted"), bid.payment_terms),
            (_("Warranty"), bid.warranty_notes),
            (_("Commercial notes"), bid.commercial_notes),
        ]
        content = Markup("").join(
            Markup("<p><strong>%s:</strong> %s</p>") % (escape(label), escape(value))
            for label, value in sections if value
        )
        return Markup("<p><strong>%s</strong> %s</p>") % (
            escape(_("SEDAR Bid:")), escape(bid.name),
        ) + content

    def _prepare_grouped_order_values(self, bid, fiscal_position):
        partner = bid.bidder_id.with_company(self.company_id)
        return {
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "user_id": self._get_valid_officer().id,
            "origin": self.name,
            "fiscal_position_id": fiscal_position.id,
            "payment_term_id": partner.property_supplier_payment_term_id.id,
            "note": self._purchase_order_notes(bid),
            "sedar_purchase_request_id": self.id,
            "sedar_bid_id": bid.id,
        }

    def _prepare_grouped_order_line_values(self, order, award, fiscal_position):
        promised_date = award.bid_line_id.promised_delivery_date or award.bid_id.promised_delivery_date
        date_planned = (
            _company_midnight_utc(self.company_id, promised_date)
            if promised_date else self.required_date
        )
        taxes = self._mapped_supplier_taxes(award, fiscal_position)
        return {
            "order_id": order.id,
            "product_id": award.product_id.id,
            "name": award.product_id.display_name,
            "product_qty": award.quantity,
            "product_uom_id": award.product_uom_id.id,
            "price_unit": award.unit_price,
            "technical_price_unit": award.unit_price,
            "discount": 0.0,
            "date_planned": date_planned,
            "tax_ids": [Command.set(taxes.ids)],
            "sedar_purchase_request_line_id": award.request_line_id.id,
            "sedar_bid_line_id": award.bid_line_id.id,
            "sedar_line_award_id": award.id,
        }

    def action_create_purchase_orders(self):
        self.ensure_one()
        self._check_procurement_inventory_officer()
        self.env.cr.execute(
            "SELECT id FROM sedar_purchase_request WHERE id = %s FOR UPDATE", [self.id]
        )
        self.env.cr.execute(
            "SELECT id FROM sedar_purchase_request_line WHERE request_id = %s ORDER BY id FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()
        existing_orders = self.sudo().purchase_order_ids | self.sudo().purchase_order_id
        legacy_orders = existing_orders.filtered(lambda order: not order.sedar_bid_id)
        if legacy_orders:
            return self._action_open_purchase_orders(existing_orders)
        active_lines = self._validate_awards_for_handoff()
        grouped_awards = defaultdict(lambda: self.env["sedar.purchase.line.award"])
        for award in active_lines.mapped("current_award_id"):
            grouped_awards[award.bid_id] |= award
        created_orders = self.env["purchase.order"]
        created_any = False
        with self.env.cr.savepoint():
            for bid, awards in grouped_awards.items():
                order = self.env["purchase.order"].sudo().search([
                    ("sedar_purchase_request_id", "=", self.id),
                    ("sedar_bid_id", "=", bid.id),
                ], limit=1)
                if order and awards.filtered(
                    lambda award: not award.purchase_order_line_id
                    or award.purchase_order_line_id.order_id != order
                ):
                    raise UserError(_(
                        "An existing grouped Purchase Order has incomplete award traceability. Recover it before retrying."
                    ))
                if not order:
                    created_any = True
                    fiscal_position = self.env["account.fiscal.position"].with_company(
                        self.company_id
                    )._get_fiscal_position(bid.bidder_id)
                    order = self.env["purchase.order"].with_company(self.company_id).sudo().with_context(
                        **{AWARD_INTERNAL_CONTEXT: True}
                    ).create(self._prepare_grouped_order_values(bid, fiscal_position))
                    for award in awards:
                        line = self.env["purchase.order.line"].with_company(self.company_id).sudo().with_context(
                            **{AWARD_INTERNAL_CONTEXT: True}, skip_uom_conversion=True,
                        ).create(self._prepare_grouped_order_line_values(order, award, fiscal_position))
                        award.sudo().with_context(**{AWARD_INTERNAL_CONTEXT: True}).write({
                            "state": "ordered", "purchase_order_line_id": line.id,
                        })
                created_orders |= order
            self.sudo().write({"state": "po_created"})
        if created_any:
            self.message_post(body=Markup("<p>%s</p>") % escape(_(
                "Created %(count)s grouped Purchase Order(s) from approved Line Awards.",
                count=len(created_orders),
            )))
        return self._action_open_purchase_orders(created_orders)


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
        if self.line_state != "active" or self.current_award_id:
            raise UserError(_("Only an active unawarded line can be cancelled."))
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
        if request.state != "approved" or self.line_state != "active" or self.current_award_id:
            raise UserError(_("Only an active unawarded line on an approved request can be cancelled."))
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

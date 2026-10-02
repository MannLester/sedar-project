from collections import defaultdict
from markupsafe import Markup, escape
from odoo import _, Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from .purchase_award_common import AWARD_INTERNAL_CONTEXT, RECOVERY_AUDIT_FIELDS, _company_midnight_utc


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
    winning_bidder_ids = fields.Many2many(
        "res.partner", compute="_compute_current_award_summary", compute_sudo=True,
        string="Winning Bidders",
        groups="sedar_marine_inventory.group_marine_inventory_manager",
    )
    awarded_total = fields.Monetary(
        compute="_compute_current_award_summary", compute_sudo=True,
        currency_field="currency_id", string="Awarded Value",
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

    @api.depends(
        "line_ids.line_state",
        "line_ids.current_award_id.state",
        "line_ids.current_award_id.bidder_id",
        "line_ids.current_award_id.quantity",
        "line_ids.current_award_id.unit_price",
        "currency_id",
    )
    def _compute_current_award_summary(self):
        for request in self:
            awards = request.sudo().line_ids.filtered(
                lambda line: line.line_state == "active"
                and line.current_award_id.state in {"awarded", "ordered"}
            ).mapped("current_award_id")
            request.winning_bidder_ids = awards.mapped("bidder_id")
            amount = sum(award.quantity * award.unit_price for award in awards)
            request.awarded_total = (
                request.currency_id.round(amount) if request.currency_id else amount
            )

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
            "context": {
                "search_default_group_request": 1,
                "search_default_group_request_line": 2,
            },
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

    def _purchase_order_notes(self, bid, awards):
        sections = [
            (_("Delivery terms"), bid.delivery_terms),
            (_("Availability"), bid.availability_notes),
            (_("Payment terms quoted"), bid.payment_terms),
            (_("Warranty"), bid.warranty_notes),
            (_("Commercial notes"), bid.commercial_notes),
        ]
        content = Markup("").join(
            Markup("<p><strong>%s:</strong> %s</p>") % (escape(label), escape(value))
            for label, value in sections if value
        )
        header = Markup("<p><strong>%s</strong> %s</p>") % (
            escape(_("SEDAR Bid:")), escape(bid.name),
        ) + content

        line_content = Markup("")
        for award in awards:
            bid_line = award.bid_line_id
            line_sections = [
                (_("Availability"), bid_line.availability_note),
                (_("Delivery terms"), bid_line.delivery_terms),
                (_("Notes"), bid_line.notes),
            ]
            if not any(value for _label, value in line_sections):
                continue
            line_content += Markup("<p><strong>%s</strong></p>") % escape(_(
                "Winning line: %(product)s",
                product=award.product_id.display_name,
            ))
            line_content += Markup("").join(
                Markup("<p><strong>%s:</strong> %s</p>") % (
                    escape(label), escape(value),
                )
                for label, value in line_sections if value
            )
        return header + line_content

    def _prepare_grouped_order_values(self, bid, awards, fiscal_position):
        partner = bid.bidder_id.with_company(self.company_id)
        return {
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "user_id": self._get_valid_officer().id,
            "origin": self.name,
            "fiscal_position_id": fiscal_position.id,
            "payment_term_id": partner.property_supplier_payment_term_id.id,
            "note": self._purchase_order_notes(bid, awards),
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
                    ).create(self._prepare_grouped_order_values(
                        bid, awards, fiscal_position,
                    ))
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

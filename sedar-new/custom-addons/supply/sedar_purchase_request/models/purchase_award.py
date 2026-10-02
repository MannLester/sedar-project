from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from .purchase_award_common import AWARD_INTERNAL_CONTEXT, AWARD_MUTABLE_FIELDS


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

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError


BID_MODEL = "sedar.purchase.bid"
BID_LINK_FIELDS = {"res_model", "res_id", "res_field"}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _sedar_bid_targets(self, vals=None):
        """Return current and proposed Bid targets for attachment mutations."""
        vals = vals or {}
        bid_ids = set()
        for attachment in self.sudo():
            if attachment.res_model == BID_MODEL and attachment.res_id:
                bid_ids.add(attachment.res_id)
            target_model = vals.get("res_model", attachment.res_model)
            target_id = vals.get("res_id", attachment.res_id)
            if target_model == BID_MODEL and target_id:
                bid_ids.add(target_id)
        if not self and vals.get("res_model") == BID_MODEL and vals.get("res_id"):
            bid_ids.add(vals["res_id"])
        return self.env[BID_MODEL].sudo().browse(bid_ids).exists()

    def _check_sedar_bid_attachment_mutation(self, vals=None):
        bids = self._sedar_bid_targets(vals)
        if not bids:
            return
        vals = vals or {}
        if vals.get("public") or vals.get("access_token") or vals.get("url"):
            raise ValidationError(_(
                "Bid quotations cannot be public, token-accessible, or URL attachments."
            ))
        if vals.get("type") not in (None, False, "binary"):
            raise ValidationError(_("Bid quotations must be private binary attachments."))
        if not self.env.su:
            unauthorized = bids.filtered(
                lambda bid: self.env.user
                != bid.request_id.company_id.sedar_procurement_inventory_officer_id
            )
            if unauthorized:
                raise AccessError(_(
                    "Only the configured Procurement and Inventory Officer may maintain Bid quotations."
                ))
            if bids.filtered(lambda bid: bid.state != "draft"):
                raise AccessError(_(
                    "A received or withdrawn Bid quotation is immutable."
                ))
            if self and BID_LINK_FIELDS.intersection(vals):
                raise AccessError(_("Bid quotation attachments cannot be reassigned."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.browse()._check_sedar_bid_attachment_mutation(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_sedar_bid_attachment_mutation(vals)
        return super().write(vals)

    def unlink(self):
        self._check_sedar_bid_attachment_mutation()
        return super().unlink()

    @api.constrains("res_model", "res_id", "public", "access_token", "type", "url")
    def _check_sedar_bid_attachment_privacy(self):
        for attachment in self:
            if attachment.res_model != BID_MODEL or not attachment.res_id:
                continue
            if (
                attachment.public
                or attachment.access_token
                or attachment.url
                or attachment.type != "binary"
            ):
                raise ValidationError(_(
                    "Bid quotations must remain private binary attachments without access tokens."
                ))


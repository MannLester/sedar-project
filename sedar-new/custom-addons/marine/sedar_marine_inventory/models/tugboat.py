from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SedarTugboat(models.Model):
    _inherit = "sedar.tugboat"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Tugboat Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        check_company=True,
        help="Internal Inventory location representing fuel, lubricant, and onboard stores assigned to this tugboat.",
    )
    onboard_stock_item_count = fields.Integer(compute="_compute_onboard_stock_item_count")

    @api.constrains("company_id", "stock_location_id")
    def _check_sedar_stock_location(self):
        for tugboat in self.filtered("stock_location_id"):
            location = tugboat.stock_location_id
            if (
                location.company_id != tugboat.company_id
                or location.sedar_location_role != "tug"
                or location.sedar_tugboat_id != tugboat
            ):
                raise ValidationError(
                    _(
                        "A tugboat stock location must be the tagged company location linked to that tugboat."
                    )
                )

    @api.depends("stock_location_id")
    def _compute_onboard_stock_item_count(self):
        Quant = self.env["stock.quant"]
        for tugboat in self:
            tugboat.onboard_stock_item_count = Quant.search_count([
                ("location_id", "=", tugboat.stock_location_id.id),
                ("quantity", ">", 0),
            ]) if tugboat.stock_location_id else 0

    def action_open_onboard_stock(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "%s Onboard Stock" % self.display_name,
            "res_model": "stock.quant",
            "view_mode": "list",
            "domain": [("location_id", "=", self.stock_location_id.id)],
            "context": {"search_default_internal_loc": 1},
            "target": "current",
        }

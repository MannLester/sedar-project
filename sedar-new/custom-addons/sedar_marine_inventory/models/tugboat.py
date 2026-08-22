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

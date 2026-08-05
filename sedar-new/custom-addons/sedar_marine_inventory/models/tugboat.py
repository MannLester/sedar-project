from odoo import fields, models


class SedarTugboat(models.Model):
    _inherit = "sedar.tugboat"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Tugboat Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal Inventory location representing fuel, lubricant, and onboard stores assigned to this tugboat.",
    )

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    sedar_service_order_id = fields.Many2one(
        "sedar.marine.service.order",
        string="Marine Service Order",
        copy=False,
        index=True,
        ondelete="restrict",
    )

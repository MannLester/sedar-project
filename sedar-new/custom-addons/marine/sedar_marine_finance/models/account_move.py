from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    sedar_service_order_id = fields.Many2one(
        "sedar.marine.service.order",
        string="Marine Service Order",
        copy=False,
        index=True,
        ondelete="restrict",
        check_company=True,
    )

    @api.constrains("company_id", "sedar_service_order_id")
    def _check_sedar_service_order_company(self):
        for move in self:
            if (
                move.sedar_service_order_id
                and move.sedar_service_order_id.company_id != move.company_id
            ):
                raise ValidationError(_(
                    "The Marine Service Order must belong to the invoice company."
                ))

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def sedar_configure_demo_currency(self):
        company = self.env.ref("base.main_company")
        php = self.env.ref("base.PHP")
        if company.currency_id != php and not self.env["account.move.line"].search_count([]):
            company.currency_id = php

        self.env["sedar.marine.service.type"].sudo().search([]).write({"currency_id": php.id})
        self.env["sedar.client.tariff"].sudo().with_context(
            sedar_tariff_supersede=True
        ).search([]).write({"currency_id": php.id})

        orders = self.env["sedar.marine.service.order"].sudo().search([])
        orders.with_context(sedar_finance_internal=True).write({"currency_id": php.id})
        frozen_orders = orders.filtered("pricing_frozen_at")
        frozen_orders.with_context(sedar_finance_internal=True).write(
            {"confirmed_currency_id": php.id}
        )
        return True

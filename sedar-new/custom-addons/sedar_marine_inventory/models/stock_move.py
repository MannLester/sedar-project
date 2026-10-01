from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _sedar_refresh_linked_readiness(self):
        products = self.mapped("product_id")
        locations = self.mapped("location_id") | self.mapped("location_dest_id")
        if not products or not locations:
            return

        requirements = self.env["sedar.inventory.requirement"].search([
            ("product_id", "in", products.ids),
            "|",
            ("source_location_id", "in", locations.ids),
            ("tug_location_id", "in", locations.ids),
        ])
        if requirements:
            requirements._compute_stock_status()
            orders = requirements.mapped("order_id")
            orders._compute_inventory_summary()
            orders._sync_inventory_readiness()
            orders._compute_readiness()
            orders._sync_automated_readiness()

        part_lines = self.env["sedar.maintenance.part.line"].search([
            ("product_id", "in", products.ids),
            ("source_location_id", "in", locations.ids),
        ])
        if part_lines:
            part_lines._compute_state()

    def _action_done(self, *args, **kwargs):
        result = super()._action_done(*args, **kwargs)
        self._sedar_refresh_linked_readiness()
        return result

    def _action_cancel(self, *args, **kwargs):
        result = super()._action_cancel(*args, **kwargs)
        self._sedar_refresh_linked_readiness()
        return result

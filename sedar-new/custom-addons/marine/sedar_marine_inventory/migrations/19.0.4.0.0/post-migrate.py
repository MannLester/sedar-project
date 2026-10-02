from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute stock-derived states after expanding the readiness selection."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    requirements = env["sedar.inventory.requirement"].with_context(active_test=False).search([])
    requirements._compute_stock_status()
    orders = requirements.mapped("order_id")
    orders._compute_inventory_summary()
    orders._sync_inventory_readiness()
    orders.sync_automated_readiness()

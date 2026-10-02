from odoo import SUPERUSER_ID, api


LEGACY_INVENTORY_MENUS = (
    "sedar_marine_inventory.menu_marine_inventory_root",
    "sedar_marine_inventory.menu_inventory_check",
    "sedar_marine_inventory.menu_inventory_currently_in_use",
    "sedar_marine_inventory.menu_inventory_issues",
    "sedar_marine_inventory.menu_inventory_requirements",
    "sedar_marine_inventory.menu_inventory_templates",
)


def migrate(cr, version):
    """Converge upgraded databases on the single Procurement workspace tree."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    menus = env["ir.ui.menu"]
    for xmlid in LEGACY_INVENTORY_MENUS:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menus |= menu
    menus.write({"active": False})

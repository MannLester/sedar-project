from odoo import SUPERUSER_ID, api

from odoo.addons.sedar_demo_suite.hooks import _ensure_inventory_lifecycle_demo


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_inventory_lifecycle_demo(env)

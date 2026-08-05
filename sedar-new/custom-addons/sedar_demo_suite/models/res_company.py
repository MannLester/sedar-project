from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_reconcile_demo_suite(self):
        from ..hooks import post_init_hook
        post_init_hook(self.env)
        return True

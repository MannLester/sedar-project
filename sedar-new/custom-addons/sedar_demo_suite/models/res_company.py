from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_reconcile_demo_suite(self):
        from ..hooks import post_init_hook
        for company in self:
            company_env = self.env["res.company"].with_company(company).env
            post_init_hook(company_env)
        return True

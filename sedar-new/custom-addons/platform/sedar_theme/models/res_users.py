from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def sedar_set_default_home_action(self):
        action = self.env.ref("sedar_marine_operations.action_service_order_dashboard", raise_if_not_found=False)
        if not action:
            return False

        users = self.search([("share", "=", False)])
        users.write({"action_id": action.id})
        return True

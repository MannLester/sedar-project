from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def sedar_set_default_home_action(self):
        action = self.env.ref("sedar_owner_preview.action_owner_preview_dashboard", raise_if_not_found=False)
        if not action:
            return False

        users = self.search([("share", "=", False)])
        users.write({"action_id": action.id})
        return True

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    sedar_maintenance_fallback_user_id = fields.Many2one(
        "res.users",
        string="Maintenance Alert Fallback",
        domain="[('active', '=', True), ('share', '=', False)]",
        help="Receives Equipment running-hour alerts when no active technician is assigned.",
    )

    @api.constrains("sedar_maintenance_fallback_user_id")
    def _check_sedar_maintenance_fallback_user(self):
        for company in self:
            user = company.sedar_maintenance_fallback_user_id
            if user and (not user.active or user.share or company not in user.company_ids):
                raise ValidationError(_(
                    "The Maintenance alert fallback must be an active internal user allowed in this company."
                ))

    def write(self, vals):
        result = super().write(vals)
        if "sedar_maintenance_fallback_user_id" in vals:
            self.env["maintenance.equipment"].search([
                ("company_id", "in", self.ids),
                ("sedar_service_due_state", "in", ["due", "overdue"]),
            ])._sedar_reconcile_due_activity()
        return result


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sedar_maintenance_fallback_user_id = fields.Many2one(
        related="company_id.sedar_maintenance_fallback_user_id", readonly=False
    )

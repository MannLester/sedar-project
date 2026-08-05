from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    sedar_crew_unavailability_id = fields.Many2one(
        "sedar.crew.unavailability",
        string="Crew Unavailability",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("sedar_leave_sync") and {"state", "date_from", "date_to", "employee_id"}.intersection(vals):
            self._sedar_sync_crew_unavailability()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves._sedar_sync_crew_unavailability()
        return leaves

    def _sedar_sync_crew_unavailability(self):
        profile_model = self.env["sedar.crew.profile"].sudo()
        unavailability_model = self.env["sedar.crew.unavailability"].sudo()
        for leave in self.sudo():
            profile = profile_model.search([("employee_id", "=", leave.employee_id.id)], limit=1)
            if not profile:
                continue
            if leave.state in {"validate", "validate1"}:
                values = {
                    "crew_profile_id": profile.id,
                    "source": "leave",
                    "leave_id": leave.id,
                    "date_start": leave.date_from,
                    "date_end": leave.date_to,
                    "state": "planned",
                    "reason": leave.holiday_status_id.name or "Approved leave",
                    "notes": leave.name,
                }
                if leave.sedar_crew_unavailability_id:
                    leave.sedar_crew_unavailability_id.write(values)
                else:
                    leave.with_context(sedar_leave_sync=True).write({
                        "sedar_crew_unavailability_id": unavailability_model.create(values).id
                    })
            elif leave.sedar_crew_unavailability_id:
                leave.sedar_crew_unavailability_id.write({"state": "cancelled"})

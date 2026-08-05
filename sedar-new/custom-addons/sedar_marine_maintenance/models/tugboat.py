from odoo import api, fields, models


class SedarTugboat(models.Model):
    _inherit = "sedar.tugboat"

    maintenance_equipment_ids = fields.One2many(
        "maintenance.equipment",
        "sedar_tugboat_id",
        string="Marine Equipment",
    )
    maintenance_request_ids = fields.One2many(
        "maintenance.request",
        "sedar_tugboat_id",
        string="Maintenance Work Orders",
    )
    drydock_plan_ids = fields.One2many(
        "sedar.drydock.plan",
        "tugboat_id",
        string="Dry Dock Plans",
    )
    open_maintenance_blocker_count = fields.Integer(
        compute="_compute_maintenance_blockers",
        store=True,
    )
    maintenance_readiness_reason = fields.Char(
        compute="_compute_maintenance_blockers",
        store=True,
    )

    @api.depends(
        "maintenance_request_ids.sedar_availability_impact",
        "maintenance_request_ids.close_date",
        "drydock_plan_ids.state",
        "drydock_plan_ids.availability_impact",
    )
    def _compute_maintenance_blockers(self):
        for tugboat in self:
            requests = tugboat.maintenance_request_ids.filtered(
                lambda request: request.sedar_blocks_tug_readiness
            )
            drydocks = tugboat.drydock_plan_ids.filtered("sedar_blocks_tug_readiness")
            tugboat.open_maintenance_blocker_count = len(requests) + len(drydocks)
            reasons = (requests.mapped("name") + drydocks.mapped("name"))[:3]
            tugboat.maintenance_readiness_reason = ", ".join(reasons)

    def _sedar_has_maintenance_blockers(self):
        self.ensure_one()
        return bool(self.open_maintenance_blocker_count)

    def _sedar_sync_maintenance_availability(self):
        for tugboat in self:
            tugboat.invalidate_recordset([
                "open_maintenance_blocker_count",
                "maintenance_readiness_reason",
            ])
            if tugboat._sedar_has_maintenance_blockers():
                if tugboat.availability_status != "maintenance":
                    tugboat.availability_status = "maintenance"
            elif tugboat.availability_status == "maintenance":
                tugboat.availability_status = "available"
        return True

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    sedar_tugboat_id = fields.Many2one(
        "sedar.tugboat",
        string="Tugboat",
        index=True,
        ondelete="restrict",
    )
    sedar_work_order_type = fields.Selection(
        [
            ("planned", "Planned Maintenance"),
            ("defect", "Defect / Corrective"),
            ("drydock", "Dry Dock Work"),
        ],
        string="SEDAR Work Type",
        default="defect",
        required=True,
    )
    sedar_priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
    )
    sedar_defect_source = fields.Char(string="Defect Source")
    sedar_availability_impact = fields.Selection(
        [
            ("none", "No Availability Impact"),
            ("advisory", "Monitor Only"),
            ("blocking", "Blocks Tug Readiness"),
        ],
        string="Availability Impact",
        default="none",
        required=True,
    )
    sedar_blocks_tug_readiness = fields.Boolean(
        compute="_compute_sedar_blocks_tug_readiness",
        store=True,
    )
    sedar_drydock_plan_id = fields.Many2one(
        "sedar.drydock.plan",
        string="Dry Dock Plan",
        ondelete="set null",
    )
    sedar_spare_part_note = fields.Text(
        string="Spare Parts Note",
        help="Visible placeholder until Slice 11 connects maintenance to Inventory stock reservations.",
    )
    sedar_running_hours_at_service = fields.Float(string="Running Hours at Service")
    sedar_closure_note = fields.Text(string="Verification / Closure Note")
    sedar_released_by_id = fields.Many2one("res.users", string="Released By", readonly=True, copy=False)
    sedar_released_at = fields.Datetime(string="Released At", readonly=True, copy=False)

    @api.onchange("equipment_id")
    def _onchange_equipment_id(self):
        if self.equipment_id.sedar_tugboat_id:
            self.sedar_tugboat_id = self.equipment_id.sedar_tugboat_id

    @api.depends("sedar_availability_impact", "close_date")
    def _compute_sedar_blocks_tug_readiness(self):
        for request in self:
            request.sedar_blocks_tug_readiness = (
                request.sedar_availability_impact == "blocking" and not request.close_date
            )

    @api.constrains("sedar_availability_impact", "sedar_tugboat_id", "sedar_work_order_type")
    def _check_marine_maintenance_required_fields(self):
        for request in self:
            if request.sedar_availability_impact == "blocking" and not request.sedar_tugboat_id:
                raise ValidationError("A blocking marine maintenance work order must identify the affected tugboat.")
            if request.sedar_work_order_type == "defect" and not request.sedar_defect_source:
                raise ValidationError("Defect work orders require a defect source.")

    def _check_maintenance_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_marine_maintenance.group_marine_maintenance_manager"):
            raise AccessError("Only a Marine Maintenance Manager may release technical availability holds.")

    def action_sedar_mark_blocking(self):
        self._check_maintenance_manager()
        for request in self:
            if not request.sedar_tugboat_id:
                raise UserError("Set the affected tugboat before marking this work order as blocking.")
            request.write({"sedar_availability_impact": "blocking"})
        self.mapped("sedar_tugboat_id")._sedar_sync_maintenance_availability()
        return True

    def action_sedar_release_tug(self):
        self._check_maintenance_manager()
        for request in self:
            if not request.sedar_closure_note:
                raise UserError("Enter a verification or closure note before releasing the tugboat.")
            request.write({
                "sedar_availability_impact": "none",
                "close_date": request.close_date or fields.Datetime.now(),
                "sedar_released_by_id": self.env.user.id,
                "sedar_released_at": fields.Datetime.now(),
            })
        self.mapped("sedar_tugboat_id")._sedar_sync_maintenance_availability()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("equipment_id") and not vals.get("sedar_tugboat_id"):
                equipment = self.env["maintenance.equipment"].browse(vals["equipment_id"])
                vals["sedar_tugboat_id"] = equipment.sedar_tugboat_id.id
        requests = super().create(vals_list)
        requests.mapped("sedar_tugboat_id")._sedar_sync_maintenance_availability()
        return requests

    def write(self, vals):
        old_tugs = self.mapped("sedar_tugboat_id")
        if vals.get("equipment_id") and not vals.get("sedar_tugboat_id"):
            equipment = self.env["maintenance.equipment"].browse(vals["equipment_id"])
            vals = dict(vals, sedar_tugboat_id=equipment.sedar_tugboat_id.id)
        result = super().write(vals)
        if {"sedar_availability_impact", "close_date", "sedar_tugboat_id", "equipment_id"}.intersection(vals):
            (old_tugs | self.mapped("sedar_tugboat_id"))._sedar_sync_maintenance_availability()
        return result

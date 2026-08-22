from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


SERVICE_BASELINE_AUDIT_FIELDS = {
    "sedar_running_hours_at_service",
    "sedar_service_baseline_verified_by_id",
    "sedar_service_baseline_verified_at",
}


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
    sedar_service_reading_id = fields.Many2one(
        "sedar.equipment.running.hour.reading",
        string="Service Running Hour Reading",
        copy=False,
        ondelete="restrict",
        check_company=True,
        domain="[('equipment_id', '=', equipment_id), ('state', '=', 'valid')]",
    )
    sedar_running_hours_at_service = fields.Float(
        string="Verified Running Hours at Service",
        readonly=True,
        copy=False,
    )
    sedar_service_baseline_verified_by_id = fields.Many2one(
        "res.users",
        string="Service Baseline Verified By",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    sedar_service_baseline_verified_at = fields.Datetime(
        string="Service Baseline Verified At",
        readonly=True,
        copy=False,
    )
    sedar_stage_done = fields.Boolean(
        string="Work Order Completed",
        related="stage_id.done",
        readonly=True,
    )
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

    def action_sedar_verify_service_baseline(self):
        self._check_maintenance_manager()
        if self.ids:
            self.env.cr.execute(
                "SELECT id FROM maintenance_request WHERE id IN %s FOR UPDATE",
                [tuple(self.ids)],
            )
        for request in self:
            if request._service_baseline_is_already_current():
                continue
            reading = request._validate_service_baseline()
            equipment = request.equipment_id

            request.sudo().write({
                "sedar_running_hours_at_service": reading.running_hours,
                "sedar_service_baseline_verified_by_id": self.env.user.id,
                "sedar_service_baseline_verified_at": fields.Datetime.now(),
            })
            equipment.sudo().write({
                "sedar_verified_service_reading_id": reading.id,
                "sedar_verified_service_work_order_id": request.id,
                "sedar_last_service_date": fields.Date.to_date(reading.reading_at),
                "sedar_last_service_hours": reading.running_hours,
            })
            equipment._sedar_reconcile_due_activity()
        return True

    def _service_baseline_is_already_current(self):
        self.ensure_one()
        if not self.sedar_service_baseline_verified_at:
            return False
        if (
            self.equipment_id.sedar_verified_service_work_order_id == self
            and self.equipment_id.sedar_verified_service_reading_id
            == self.sedar_service_reading_id
        ):
            return True
        raise UserError("This planned-maintenance service baseline is already verified.")

    def _validate_service_baseline(self):
        self.ensure_one()
        if self.sedar_work_order_type != "planned":
            raise UserError("Only completed planned-maintenance work may establish a service baseline.")
        if not self.stage_id.done:
            raise UserError("Complete the planned-maintenance work order before verifying its service baseline.")
        if not self.equipment_id:
            raise UserError("Select the serviced Equipment before verifying the service baseline.")
        reading = self.sedar_service_reading_id
        if not reading or reading.state != "valid":
            raise UserError("Select a valid Running Hour Reading for the completed service.")
        if reading.equipment_id != self.equipment_id:
            raise ValidationError("The service reading must belong to the work order's Equipment.")
        existing = self.equipment_id.sedar_verified_service_reading_id
        if existing and existing.reading_at > reading.reading_at:
            raise UserError(
                "This Equipment already has a newer verified service baseline. Correct that workflow instead."
            )
        return reading

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
        if not self.env.su and any(
            SERVICE_BASELINE_AUDIT_FIELDS.intersection(vals) for vals in vals_list
        ):
            raise AccessError(
                "Verified service audit fields are set only by the baseline verification workflow."
            )
        for vals in vals_list:
            if vals.get("equipment_id") and not vals.get("sedar_tugboat_id"):
                equipment = self.env["maintenance.equipment"].browse(vals["equipment_id"])
                vals["sedar_tugboat_id"] = equipment.sedar_tugboat_id.id
        requests = super().create(vals_list)
        requests.mapped("sedar_tugboat_id")._sedar_sync_maintenance_availability()
        return requests

    def write(self, vals):
        if SERVICE_BASELINE_AUDIT_FIELDS.intersection(vals) and not self.env.su:
            raise AccessError(
                "Verified service audit fields are changed only by the baseline verification workflow."
            )
        if self.filtered("sedar_service_baseline_verified_at") and {
            "equipment_id",
            "sedar_service_reading_id",
            "sedar_work_order_type",
        }.intersection(vals) and not self.env.su:
            raise AccessError("A verified service baseline cannot be silently reassigned or edited.")
        old_tugs = self.mapped("sedar_tugboat_id")
        if vals.get("equipment_id") and not vals.get("sedar_tugboat_id"):
            equipment = self.env["maintenance.equipment"].browse(vals["equipment_id"])
            vals = dict(vals, sedar_tugboat_id=equipment.sedar_tugboat_id.id)
        result = super().write(vals)
        if {"sedar_availability_impact", "close_date", "sedar_tugboat_id", "equipment_id"}.intersection(vals):
            (old_tugs | self.mapped("sedar_tugboat_id"))._sedar_sync_maintenance_availability()
        return result

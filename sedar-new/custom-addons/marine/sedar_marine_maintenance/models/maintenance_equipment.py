from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

PM_STATE_RANK = {"unconfigured": 0, "not_due": 1, "approaching": 2, "due": 3, "overdue": 4}


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    sedar_tugboat_id = fields.Many2one(
        "sedar.tugboat", string="Tugboat", index=True, ondelete="restrict",
        check_company=True,
    )
    sedar_parent_equipment_id = fields.Many2one(
        "maintenance.equipment", string="Parent Marine Equipment", ondelete="restrict"
    )
    sedar_child_equipment_ids = fields.One2many(
        "maintenance.equipment", "sedar_parent_equipment_id", string="Sub Equipment"
    )
    sedar_system = fields.Selection(
        [
            ("propulsion", "Propulsion"),
            ("electrical", "Electrical"),
            ("navigation", "Navigation"),
            ("hull", "Hull"),
            ("deck", "Deck Machinery"),
            ("safety", "Safety"),
            ("auxiliary", "Auxiliary"),
            ("other", "Other"),
        ],
        string="Marine System",
        default="other",
    )
    sedar_criticality = fields.Selection(
        [("critical", "Critical"), ("major", "Major"), ("minor", "Minor")],
        string="Criticality",
        default="major",
        required=True,
    )
    sedar_installation_date = fields.Date(string="Installation Date")
    sedar_hours_from_id = fields.Many2one(
        "maintenance.equipment",
        string="Running Hours From",
        domain="[('sedar_tugboat_id', '=', sedar_tugboat_id), ('sedar_hours_from_id', '=', False), ('id', '!=', id)]",
        ondelete="restrict",
        help="Component that shares another Equipment's running hours, such as a part of a main engine.",
    )
    sedar_running_hour_reading_ids = fields.One2many(
        "sedar.equipment.running.hour.reading",
        "equipment_id",
        string="Running Hour Readings",
        copy=False,
    )
    sedar_current_running_hour_reading_id = fields.Many2one(
        "sedar.equipment.running.hour.reading",
        string="Current Reading",
        compute="_compute_sedar_running_hours",
        store=True,
        readonly=True,
        copy=False,
    )
    sedar_current_running_hours = fields.Float(
        string="Current Running Hours",
        compute="_compute_sedar_running_hours",
        store=True,
        readonly=True,
    )
    sedar_pm_task_ids = fields.One2many(
        "sedar.pm.task", "equipment_id", string="Planned Maintenance Tasks"
    )
    sedar_service_due_state = fields.Selection(
        [
            ("unconfigured", "No Tasks"),
            ("not_due", "Not Due"),
            ("approaching", "Approaching"),
            ("due", "Due"),
            ("overdue", "Overdue"),
        ],
        string="Service Status",
        compute="_compute_sedar_pm_summary",
        store=True,
        readonly=True,
        default="unconfigured",
    )
    sedar_next_service_hours = fields.Float(
        string="Next Service Hours",
        compute="_compute_sedar_pm_summary",
        store=True,
        readonly=True,
        help="Running hours of the nearest upcoming Planned Maintenance checkpoint.",
    )

    @api.depends(
        "sedar_running_hour_reading_ids.state",
        "sedar_running_hour_reading_ids.reading_at",
        "sedar_running_hour_reading_ids.running_hours",
        "sedar_hours_from_id.sedar_running_hour_reading_ids.state",
        "sedar_hours_from_id.sedar_running_hour_reading_ids.reading_at",
        "sedar_hours_from_id.sedar_running_hour_reading_ids.running_hours",
    )
    def _compute_sedar_running_hours(self):
        for equipment in self:
            source = equipment.sedar_hours_from_id or equipment
            current = source.sedar_running_hour_reading_ids.filtered(
                lambda reading: reading.state == "valid"
            ).sorted(key=lambda reading: (reading.reading_at, reading.id), reverse=True)[:1]
            equipment.sedar_current_running_hour_reading_id = current
            equipment.sedar_current_running_hours = current.running_hours if current else 0.0

    @api.depends("sedar_pm_task_ids.state", "sedar_pm_task_ids.next_checkpoint_hours")
    def _compute_sedar_pm_summary(self):
        for equipment in self:
            tasks = equipment.sedar_pm_task_ids
            equipment.sedar_service_due_state = max(
                tasks.mapped("state"), key=PM_STATE_RANK.get, default="unconfigured"
            )
            equipment.sedar_next_service_hours = min(
                tasks.mapped("next_checkpoint_hours"), default=0.0
            )

    @api.constrains("sedar_hours_from_id")
    def _check_sedar_hours_from(self):
        for equipment in self.filtered("sedar_hours_from_id"):
            source = equipment.sedar_hours_from_id
            if (
                source == equipment
                or source.sedar_hours_from_id
                or equipment.sedar_running_hour_reading_ids
                or self.search_count([("sedar_hours_from_id", "=", equipment.id)])
            ):
                raise ValidationError(_(
                    "%(equipment)s cannot follow another Equipment's running hours: the source must be a different "
                    "Equipment that keeps its own hours, and %(equipment)s must have no readings of its own.",
                    equipment=equipment.display_name,
                ))

    def _sedar_refresh_pm_alerts(self):
        """Re-evaluate Planned Maintenance alerts for this Equipment and every component sharing its hours."""
        self.env["sedar.pm.task"].with_context(active_test=False).search([
            "|", ("equipment_id", "in", self.ids), ("equipment_id.sedar_hours_from_id", "in", self.ids),
        ])._sedar_reconcile_alert()

    def write(self, vals):
        result = super().write(vals)
        if {"technician_user_id", "company_id", "sedar_hours_from_id"}.intersection(vals):
            self._sedar_refresh_pm_alerts()
        return result

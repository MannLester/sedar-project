from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare
from .maintenance_equipment_common import EQUIPMENT_SERVICE_AUDIT_FIELDS, READING_PRECISION_DIGITS


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
    sedar_running_interval_hours = fields.Float(
        string="Planned Interval Hours",
        help="Running-hour interval after the last verified planned service.",
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
        compute="_compute_sedar_running_hour_status",
        store=True,
        readonly=True,
        copy=False,
    )
    sedar_current_running_hours = fields.Float(
        string="Current Running Hours",
        compute="_compute_sedar_running_hour_status",
        store=True,
        readonly=True,
    )
    sedar_verified_service_reading_id = fields.Many2one(
        "sedar.equipment.running.hour.reading",
        string="Verified Service Reading",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )
    sedar_verified_service_work_order_id = fields.Many2one(
        "maintenance.request",
        string="Verified Service Work Order",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )
    sedar_last_service_date = fields.Date(
        string="Last Verified Service Date", readonly=True, copy=False
    )
    sedar_last_service_hours = fields.Float(
        string="Last Verified Service Hours", readonly=True, copy=False
    )
    sedar_next_service_hours = fields.Float(
        string="Next Service Hours",
        compute="_compute_sedar_running_hour_status",
        store=True,
        readonly=True,
    )
    sedar_remaining_service_hours = fields.Float(
        string="Hours Until Service",
        compute="_compute_sedar_running_hour_status",
        store=True,
        readonly=True,
        help="Positive before the threshold, zero when due, and negative when overdue.",
    )
    sedar_service_due_state = fields.Selection(
        [
            ("unconfigured", "Unconfigured"),
            ("not_due", "Not Due"),
            ("due", "Due"),
            ("overdue", "Overdue"),
        ],
        string="Service Status",
        compute="_compute_sedar_running_hour_status",
        store=True,
        readonly=True,
        default="unconfigured",
    )
    sedar_service_cycle_key = fields.Char(
        compute="_compute_sedar_running_hour_status",
        store=True,
        readonly=True,
        copy=False,
    )
    sedar_alerted_service_cycle_key = fields.Char(readonly=True, copy=False)
    sedar_due_alert_assignment_state = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("assigned", "Assigned"),
            ("unassigned", "Needs Assignee"),
        ],
        string="Alert Assignment",
        compute="_compute_sedar_due_alert_assignment_state",
        store=True,
    )

    @api.depends(
        "sedar_running_hour_reading_ids.state",
        "sedar_running_hour_reading_ids.reading_at",
        "sedar_running_hour_reading_ids.running_hours",
        "sedar_verified_service_reading_id",
        "sedar_verified_service_reading_id.state",
        "sedar_running_interval_hours",
    )
    def _compute_sedar_running_hour_status(self):
        for equipment in self:
            valid_readings = equipment.sedar_running_hour_reading_ids.filtered(
                lambda reading: reading.state == "valid"
            ).sorted(key=lambda reading: (reading.reading_at, reading.id), reverse=True)
            current = valid_readings[:1]
            equipment.sedar_current_running_hour_reading_id = current
            equipment.sedar_current_running_hours = current.running_hours if current else 0.0
            equipment.sedar_next_service_hours = 0.0
            equipment.sedar_remaining_service_hours = 0.0
            equipment.sedar_service_due_state = "unconfigured"
            equipment.sedar_service_cycle_key = False

            baseline = equipment.sedar_verified_service_reading_id
            interval = equipment.sedar_running_interval_hours
            if not current or not baseline or baseline.state != "valid" or interval <= 0:
                continue

            next_service = baseline.running_hours + interval
            remaining = next_service - current.running_hours
            comparison = float_compare(
                current.running_hours,
                next_service,
                precision_digits=READING_PRECISION_DIGITS,
            )
            equipment.sedar_next_service_hours = next_service
            equipment.sedar_remaining_service_hours = remaining
            equipment.sedar_service_due_state = (
                "not_due" if comparison < 0 else "due" if comparison == 0 else "overdue"
            )
            equipment.sedar_service_cycle_key = f"{baseline.id}:{next_service:.6f}"

    @api.depends(
        "sedar_service_due_state",
        "technician_user_id",
        "technician_user_id.active",
        "company_id.sedar_maintenance_fallback_user_id",
        "company_id.sedar_maintenance_fallback_user_id.active",
    )
    def _compute_sedar_due_alert_assignment_state(self):
        for equipment in self:
            if equipment.sedar_service_due_state not in {"due", "overdue"}:
                equipment.sedar_due_alert_assignment_state = "not_required"
            else:
                equipment.sedar_due_alert_assignment_state = (
                    "assigned" if equipment._sedar_get_due_alert_assignee() else "unassigned"
                )

    @api.constrains("sedar_running_interval_hours")
    def _check_sedar_running_interval_hours(self):
        for equipment in self:
            if equipment.sedar_running_interval_hours < 0:
                raise ValidationError(_("Planned interval hours cannot be negative."))

    def _sedar_get_due_alert_assignee(self):
        self.ensure_one()
        candidates = self.technician_user_id | self.company_id.sedar_maintenance_fallback_user_id
        return candidates.filtered(
            lambda user: user.active and not user.share and self.company_id in user.company_ids
        )[:1]

    def _sedar_open_due_activities(self):
        activity_type = self.env.ref(
            "sedar_marine_maintenance.mail_activity_type_equipment_service_due",
            raise_if_not_found=False,
        )
        if not activity_type:
            return self.env["mail.activity"]
        return self.env["mail.activity"].search([
            ("active", "=", True),
            ("activity_type_id", "=", activity_type.id),
            ("res_model", "=", self._name),
            ("res_id", "in", self.ids),
        ])

    def _sedar_reconcile_due_activity(self):
        equipment_ids = self.exists().ids
        if not equipment_ids:
            return
        self.env.cr.execute(
            "SELECT id FROM maintenance_equipment WHERE id IN %s FOR UPDATE",
            [tuple(equipment_ids)],
        )
        activity_type = self.env.ref(
            "sedar_marine_maintenance.mail_activity_type_equipment_service_due",
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        for equipment in self.browse(equipment_ids):
            equipment.invalidate_recordset([
                "sedar_service_due_state",
                "sedar_service_cycle_key",
                "sedar_alerted_service_cycle_key",
            ])
            active_due_activities = equipment._sedar_open_due_activities()
            is_due = equipment.sedar_service_due_state in {"due", "overdue"}

            if not is_due:
                if active_due_activities:
                    active_due_activities.action_feedback(
                        feedback=_(
                            "Closed automatically because the verified running-hour facts no longer show service as due."
                        )
                    )
                if equipment.sedar_alerted_service_cycle_key:
                    equipment.sudo().write({"sedar_alerted_service_cycle_key": False})
                continue

            cycle_key = equipment.sedar_service_cycle_key
            if not cycle_key or equipment.sedar_alerted_service_cycle_key == cycle_key:
                continue
            assignee = equipment._sedar_get_due_alert_assignee()
            if not assignee:
                continue

            if active_due_activities:
                active_due_activities.action_feedback(
                    feedback=_(
                        "Closed automatically because a newer verified service cycle is now authoritative."
                    )
                )
            self.env["mail.activity"].create({
                "activity_type_id": activity_type.id,
                "res_model_id": self.env["ir.model"]._get_id(self._name),
                "res_id": equipment.id,
                "user_id": assignee.id,
                "summary": _(
                    "Equipment service %(state)s",
                    state=equipment.sedar_service_due_state.replace("_", " ").title(),
                ),
                "note": _(
                    "%(equipment)s has %(current).2f running hours. Its verified service threshold is %(threshold).2f hours.",
                    equipment=equipment.display_name,
                    current=equipment.sedar_current_running_hours,
                    threshold=equipment.sedar_next_service_hours,
                ),
                "date_deadline": fields.Date.context_today(equipment),
            })
            equipment.sudo().write({"sedar_alerted_service_cycle_key": cycle_key})

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(
            EQUIPMENT_SERVICE_AUDIT_FIELDS.intersection(vals) for vals in vals_list
        ):
            raise AccessError(_(
                "Verified service and due-alert audit fields are set only by their controlled workflows."
            ))
        equipment = super().create(vals_list)
        equipment._sedar_reconcile_due_activity()
        return equipment

    def write(self, vals):
        if EQUIPMENT_SERVICE_AUDIT_FIELDS.intersection(vals) and not self.env.su:
            raise AccessError(_(
                "Verified service and due-alert audit fields are changed only by their controlled workflows."
            ))
        result = super().write(vals)
        if {
            "sedar_running_interval_hours",
            "technician_user_id",
            "company_id",
        }.intersection(vals):
            self._sedar_reconcile_due_activity()
        return result

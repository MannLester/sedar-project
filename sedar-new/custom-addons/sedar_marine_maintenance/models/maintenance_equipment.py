from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


READING_PRECISION_DIGITS = 2
EQUIPMENT_SERVICE_AUDIT_FIELDS = {
    "sedar_verified_service_reading_id",
    "sedar_verified_service_work_order_id",
    "sedar_last_service_date",
    "sedar_last_service_hours",
    "sedar_alerted_service_cycle_key",
}


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    sedar_tugboat_id = fields.Many2one(
        "sedar.tugboat", string="Tugboat", index=True, ondelete="restrict"
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


class EquipmentRunningHourReading(models.Model):
    _name = "sedar.equipment.running.hour.reading"
    _description = "Equipment Running Hour Reading"
    _rec_name = "name"
    _order = "reading_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)

    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        required=True,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="equipment_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    running_hours = fields.Float(string="Running Hours", required=True)
    reading_at = fields.Datetime(
        string="Reading Time", required=True, default=fields.Datetime.now, index=True
    )
    recorded_by_id = fields.Many2one(
        "res.users",
        string="Recorded By",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    notes = fields.Text()
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "sedar_running_hour_reading_attachment_rel",
        "reading_id",
        "attachment_id",
        string="Evidence",
        copy=False,
    )
    state = fields.Selection(
        [("valid", "Valid"), ("superseded", "Superseded")],
        required=True,
        default="valid",
        readonly=True,
        index=True,
        copy=False,
    )
    supersedes_reading_id = fields.Many2one(
        "sedar.equipment.running.hour.reading",
        string="Corrects Reading",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    superseded_by_reading_ids = fields.One2many(
        "sedar.equipment.running.hour.reading",
        "supersedes_reading_id",
        string="Corrected By",
        readonly=True,
    )
    correction_reason = fields.Text(copy=False)
    superseded_by_id = fields.Many2one(
        "res.users", string="Superseded By", readonly=True, copy=False, ondelete="restrict"
    )
    superseded_at = fields.Datetime(readonly=True, copy=False)

    _one_correction_per_reading = models.Constraint(
        "unique(supersedes_reading_id)",
        "A running-hour reading may have only one direct correction.",
    )

    @api.depends("equipment_id.name", "running_hours", "reading_at", "state")
    def _compute_name(self):
        for reading in self:
            equipment_name = reading.equipment_id.display_name or _("Equipment")
            reading_time = (
                fields.Datetime.to_string(reading.reading_at)
                if reading.reading_at
                else _("No date")
            )
            state_suffix = _(" (superseded)") if reading.state == "superseded" else ""
            reading.name = _("%(equipment)s — %(hours).2f h — %(reading_time)s%(state)s") % {
                "equipment": equipment_name,
                "hours": reading.running_hours,
                "reading_time": reading_time,
                "state": state_suffix,
            }

    def _check_correction_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group(
            "sedar_marine_maintenance.group_marine_maintenance_manager"
        ):
            raise AccessError(_(
                "Only a Marine Maintenance Manager may correct a running-hour reading."
            ))

    def _validate_sedar_chronology(self, excluded_reading=None):
        self.ensure_one()
        if self.running_hours < 0:
            raise ValidationError(_("Running hours cannot be negative."))
        if self.reading_at > fields.Datetime.now():
            raise ValidationError(_("A running-hour reading cannot be dated in the future."))

        excluded_ids = (excluded_reading | self).ids if excluded_reading else self.ids
        same_time = self.search_count([
            ("equipment_id", "=", self.equipment_id.id),
            ("state", "=", "valid"),
            ("reading_at", "=", self.reading_at),
            ("id", "not in", excluded_ids),
        ])
        if same_time:
            raise ValidationError(_(
                "Only one valid reading is allowed for an Equipment at the same time."
            ))

        base_domain = [
            ("equipment_id", "=", self.equipment_id.id),
            ("state", "=", "valid"),
            ("id", "not in", excluded_ids),
        ]
        previous = self.search(
            base_domain + [("reading_at", "<", self.reading_at)],
            order="reading_at desc, id desc",
            limit=1,
        )
        following = self.search(
            base_domain + [("reading_at", ">", self.reading_at)],
            order="reading_at, id",
            limit=1,
        )
        if previous and float_compare(
            self.running_hours,
            previous.running_hours,
            precision_digits=READING_PRECISION_DIGITS,
        ) < 0:
            raise ValidationError(_(
                "Running hours cannot be lower than the preceding valid reading (%(hours).2f). "
                "A meter replacement requires a new Equipment identity.",
                hours=previous.running_hours,
            ))
        if following and float_compare(
            self.running_hours,
            following.running_hours,
            precision_digits=READING_PRECISION_DIGITS,
        ) > 0:
            raise ValidationError(_(
                "Running hours cannot be higher than the following valid reading (%(hours).2f).",
                hours=following.running_hours,
            ))

    @api.model_create_multi
    def create(self, vals_list):
        created = self.browse()
        for incoming_vals in vals_list:
            vals = dict(incoming_vals)
            if not self.env.su and {"superseded_by_id", "superseded_at"}.intersection(vals):
                raise AccessError(_(
                    "Reading correction audit fields are set only by the correction workflow."
                ))
            vals["recorded_by_id"] = self.env.user.id
            vals["state"] = "valid"
            original = self.browse(vals.get("supersedes_reading_id")).exists()
            if original:
                self._check_correction_manager()
                if original.state != "valid":
                    raise UserError(_("Only a currently valid reading may be corrected."))
                if not vals.get("correction_reason"):
                    raise ValidationError(_("A correction reason is required."))
                if vals.get("equipment_id") and vals["equipment_id"] != original.equipment_id.id:
                    raise ValidationError(_(
                        "A correction must belong to the same Equipment as the original reading."
                    ))
                vals["equipment_id"] = original.equipment_id.id
            elif vals.get("correction_reason"):
                raise ValidationError(_(
                    "A correction reason is only valid when correcting an existing reading."
                ))

            reading = super(EquipmentRunningHourReading, self).create([vals])
            reading._validate_sedar_chronology(excluded_reading=original)
            if original:
                original.sudo().write({
                    "state": "superseded",
                    "superseded_by_id": self.env.user.id,
                    "superseded_at": fields.Datetime.now(),
                })
                equipment = reading.equipment_id
                if equipment.sedar_verified_service_reading_id == original:
                    equipment.sudo().write({
                        "sedar_verified_service_reading_id": reading.id,
                        "sedar_last_service_date": fields.Date.to_date(reading.reading_at),
                        "sedar_last_service_hours": reading.running_hours,
                    })
                    equipment.sedar_verified_service_work_order_id.sudo().write({
                        "sedar_service_reading_id": reading.id,
                        "sedar_running_hours_at_service": reading.running_hours,
                    })
            reading.equipment_id._sedar_reconcile_due_activity()
            created |= reading
        return created

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_(
                "Running-hour readings are immutable. Create a correction instead."
            ))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_module_uninstall(self):
        raise UserError(_("Running-hour readings are audit history and cannot be deleted."))

    def action_sedar_correct(self):
        self.ensure_one()
        self._check_correction_manager()
        if self.state != "valid":
            raise UserError(_("Only a currently valid reading may be corrected."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Correct Running Hour Reading"),
            "res_model": self._name,
            "view_mode": "form",
            "view_id": self.env.ref(
                "sedar_marine_maintenance.view_running_hour_reading_form"
            ).id,
            "target": "current",
            "context": {
                "default_equipment_id": self.equipment_id.id,
                "default_reading_at": self.reading_at,
                "default_running_hours": self.running_hours,
                "default_supersedes_reading_id": self.id,
            },
        }

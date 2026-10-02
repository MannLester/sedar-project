from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from .maintenance_equipment_common import READING_PRECISION_DIGITS


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

            if self.env["maintenance.equipment"].browse(vals.get("equipment_id")).sedar_hours_from_id:
                raise ValidationError(_(
                    "This Equipment follows another Equipment's running hours. Record the reading on that Equipment."
                ))
            reading = super(EquipmentRunningHourReading, self).create([vals])
            reading._validate_sedar_chronology(excluded_reading=original)
            if original:
                original.sudo().write({
                    "state": "superseded",
                    "superseded_by_id": self.env.user.id,
                    "superseded_at": fields.Datetime.now(),
                })
            reading.equipment_id._sedar_refresh_pm_alerts()
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

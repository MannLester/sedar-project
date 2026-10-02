from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarCrewRotation(models.Model):
    _name = "sedar.crew.rotation"
    _description = "Crew Rotation Plan"
    _order = "date_start desc, crew_profile_id"

    name = fields.Char(compute="_compute_name", store=True)
    crew_profile_id = fields.Many2one("sedar.crew.profile", required=True, ondelete="cascade")
    employee_id = fields.Many2one(related="crew_profile_id.employee_id", store=True)
    tugboat_id = fields.Many2one("sedar.tugboat", required=True, ondelete="restrict")
    rank_id = fields.Many2one(related="crew_profile_id.rank_id", store=True)
    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime(required=True)
    watch = fields.Selection(
        [
            ("day", "Day Watch"),
            ("night", "Night Watch"),
            ("standby", "Standby"),
            ("unassigned", "Unassigned"),
        ],
        default="unassigned",
        required=True,
    )
    relief_crew_profile_id = fields.Many2one("sedar.crew.profile", string="Relief Crew")
    handover_date = fields.Datetime()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("active", "Active"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()

    @api.depends("crew_profile_id", "tugboat_id", "date_start", "date_end")
    def _compute_name(self):
        for rotation in self:
            rotation.name = "%s / %s" % (
                rotation.crew_profile_id.display_name or "Crew",
                rotation.tugboat_id.name or "Tugboat",
            )

    @api.constrains("date_start", "date_end", "handover_date")
    def _check_dates(self):
        for rotation in self:
            if rotation.date_end <= rotation.date_start:
                raise ValidationError("Rotation end must be later than the start.")
            if rotation.handover_date and not (rotation.date_start <= rotation.handover_date <= rotation.date_end):
                raise ValidationError("Handover date must fall inside the rotation period.")

    @api.constrains("crew_profile_id", "date_start", "date_end", "state")
    def _check_overlapping_rotation(self):
        for rotation in self.filtered(lambda item: item.state in {"planned", "active"}):
            overlapping = self.search_count([
                ("id", "!=", rotation.id),
                ("crew_profile_id", "=", rotation.crew_profile_id.id),
                ("state", "in", ["planned", "active"]),
                ("date_start", "<", rotation.date_end),
                ("date_end", ">", rotation.date_start),
            ])
            if overlapping:
                raise ValidationError("This Crew Profile already has an overlapping active rotation.")

    def action_plan(self):
        self.write({"state": "planned"})
        return True

    def action_activate(self):
        self.write({"state": "active"})
        return True

    def action_complete(self):
        self.write({"state": "completed"})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

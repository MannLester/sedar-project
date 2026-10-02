from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarCrewUnavailability(models.Model):
    _name = "sedar.crew.unavailability"
    _description = "Dated Crew Unavailability"
    _order = "date_start desc, crew_profile_id"

    name = fields.Char(compute="_compute_name", store=True)
    crew_profile_id = fields.Many2one("sedar.crew.profile", required=True, ondelete="cascade")
    employee_id = fields.Many2one(related="crew_profile_id.employee_id", store=True)
    source = fields.Selection(
        [
            ("leave", "Approved Leave"),
            ("medical", "Medical Restriction"),
            ("training", "Training Blocker"),
            ("temporary", "Temporary Unavailability"),
            ("other", "Other"),
        ],
        required=True,
        default="temporary",
    )
    leave_id = fields.Many2one("hr.leave", string="Time Off Request", ondelete="set null")
    shortage_id = fields.Many2one("sedar.crew.shortage", ondelete="set null")
    action_id = fields.Many2one("sedar.crew.shortage.action", ondelete="set null")
    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime()
    state = fields.Selection(
        [
            ("planned", "Planned"),
            ("active", "Active"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="planned",
    )
    reason = fields.Char(required=True)
    notes = fields.Text()

    @api.depends("crew_profile_id", "source", "date_start", "date_end")
    def _compute_name(self):
        for record in self:
            label = dict(record._fields["source"].selection).get(record.source, "Unavailable")
            record.name = "%s - %s" % (record.crew_profile_id.display_name or "Crew", label)

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_end <= record.date_start:
                raise ValidationError("Unavailability end must be later than the start.")

    def overlaps_window(self, date_start, date_end):
        self.ensure_one()
        if not date_start:
            return False
        window_end = date_end or date_start
        record_end = self.date_end or window_end
        return self.date_start < window_end and record_end > date_start

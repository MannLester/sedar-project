from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


MEASUREMENTS = ("rpm", "oil_pressure", "water_temp", "fuel_rob_start", "fuel_rob_stop")
MANAGER_GROUP = "sedar_marine_maintenance.group_marine_maintenance_manager"


def _clock(hours):
    total = round(hours * 60)
    return "%02d:%02d" % (total // 60 % 24, total % 60)


class SedarDailyEngineReport(models.Model):
    """Daily Engine Monitoring Report: one engine-room watch of one tugboat, written by the crew and approved by the Chief Engineer."""

    _name = "sedar.daily.engine.report"
    _description = "Daily Engine Monitoring Report"
    _order = "report_date desc, watch_start desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    log_key = fields.Char(
        index=True, readonly=True, copy=False,
        help="Identifier the Engine Room page gives a watch log, so a retried or resubmitted upload finds the same report.",
    )
    tugboat_id = fields.Many2one(
        "sedar.tugboat", string="Tugboat", required=True, index=True, ondelete="restrict",
    )
    company_id = fields.Many2one(related="tugboat_id.company_id", store=True, index=True)
    report_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    watch_start = fields.Float(
        string="Watch Start", help="Time of day the watch began. A watch can end after midnight.",
    )
    watch_stop = fields.Float(string="Watch Stop (Cut-off)", help="Time of day the watch was cut off.")
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("posted", "Posted")],
        default="draft", required=True, readonly=True, copy=False,
    )
    prepared_by_id = fields.Many2one(
        "res.users", string="Prepared By", readonly=True, copy=False,
        default=lambda self: self.env.user, ondelete="restrict",
    )
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    submitted_at = fields.Datetime(readonly=True, copy=False)
    return_reason = fields.Text(
        readonly=True, copy=False,
        help="Why the Chief Engineer returned the report for correction. Cleared when it is submitted again.",
    )
    posted_at = fields.Datetime(readonly=True, copy=False)
    posted_by_id = fields.Many2one(
        "res.users", string="Approved By", readonly=True, copy=False, ondelete="restrict",
        help="The Chief Engineer who approved the report.",
    )
    line_ids = fields.One2many("sedar.daily.engine.report.line", "report_id", string="Engines", copy=True)

    @api.depends("tugboat_id.name", "report_date", "watch_start", "watch_stop")
    def _compute_name(self):
        for report in self:
            report.name = _(
                "%(tug)s — %(date)s %(start)s–%(stop)s",
                tug=report.tugboat_id.name or "", date=report.report_date or "",
                start=_clock(report.watch_start), stop=_clock(report.watch_stop),
            )

    @api.constrains("report_date", "tugboat_id", "watch_start", "watch_stop")
    def _check_report(self):
        today = fields.Date.context_today(self)
        for report in self:
            if report.report_date > today:
                raise ValidationError(_("A report cannot be dated in the future."))
            if not (0 <= report.watch_start < 24 and 0 <= report.watch_stop < 24):
                raise ValidationError(_("Watch start and stop times must be within one day."))
            if self.search_count([
                ("tugboat_id", "=", report.tugboat_id.id),
                ("report_date", "=", report.report_date),
                ("watch_start", "=", report.watch_start),
                ("id", "!=", report.id),
            ]):
                raise ValidationError(_("This tugboat already has a report for a watch starting then."))

    @api.onchange("tugboat_id")
    def _onchange_tugboat_id(self):
        engines = self.env["maintenance.equipment"].search([
            ("sedar_tugboat_id", "=", self.tugboat_id.id),
            ("sedar_hours_from_id", "=", False),
            ("sedar_running_hour_reading_ids", "!=", False),
        ]) if self.tugboat_id else self.env["maintenance.equipment"]
        self.line_ids = [Command.clear()] + [Command.create({"equipment_id": engine.id}) for engine in engines]

    def _check_can_approve(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_("Only a Marine Maintenance Manager can approve or return a report."))

    def action_submit(self):
        """Hand the report to the Chief Engineer; it can no longer be edited until it is returned."""
        for report in self:
            if report.state != "draft":
                raise UserError(_("Only a draft report can be submitted."))
            if not report.line_ids:
                raise UserError(_("Add at least one engine before submitting."))
            if report.line_ids.filtered(lambda line: line.engine_status == "operated" and not line.hours_run):
                raise UserError(_("An operated engine needs a watch that stops later than it starts."))
            report.sudo().write({
                "state": "submitted", "submitted_at": fields.Datetime.now(),
                "submitted_by_id": self.env.user.id, "return_reason": False,
            })
        return True

    def action_return(self, reason=None):
        """Send a submitted report back to the crew with the reason for correction."""
        self._check_can_approve()
        if not (reason or "").strip():
            raise UserError(_("Say what needs correcting before returning the report."))
        for report in self:
            if report.state != "submitted":
                raise UserError(_("Only a submitted report can be returned."))
            report.sudo().write({"state": "draft", "return_reason": reason.strip()})
        return True

    def action_post(self):
        """Approve the report: each engine's hours become Running Hour Readings."""
        self._check_can_approve()
        for report in self:
            if report.state == "posted":
                continue
            lines = report.line_ids
            if not lines:
                raise UserError(_("Add at least one engine before posting."))
            if lines.filtered(lambda line: line.engine_status == "operated" and not line.hours_run):
                raise UserError(_("An operated engine needs a watch that stops later than it starts."))
            equipment = lines.equipment_id
            self.env.cr.execute("SELECT id FROM maintenance_equipment WHERE id IN %s FOR UPDATE", [tuple(equipment.ids)])
            equipment.invalidate_recordset(["sedar_current_running_hours"])
            for line in lines.filtered("hours_run"):
                line.sudo().reading_id = self.env["sedar.equipment.running.hour.reading"].create({
                    "equipment_id": line.equipment_id.id,
                    "running_hours": line.equipment_id.sedar_current_running_hours + line.hours_run,
                    "notes": _("Daily Engine Monitoring Report %s", report.name),
                })
            report.sudo().write({
                "state": "posted", "posted_at": fields.Datetime.now(), "posted_by_id": self.env.user.id,
                "return_reason": False,
            })
        return True

    def write(self, vals):
        if self.filtered(lambda report: report.state != "draft") and not self.env.su:
            raise AccessError(_("A submitted or posted report cannot be edited."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if self.filtered(lambda report: report.state == "posted"):
            raise UserError(_("A posted report is running-hour history and cannot be deleted."))


class SedarDailyEngineReportLine(models.Model):
    _name = "sedar.daily.engine.report.line"
    _description = "Daily Engine Monitoring Report Line"
    _order = "report_id, id"
    _check_company_auto = True

    report_id = fields.Many2one("sedar.daily.engine.report", required=True, index=True, ondelete="cascade")
    state = fields.Selection(related="report_id.state")
    company_id = fields.Many2one(related="report_id.company_id", store=True, index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Engine", required=True, ondelete="restrict", check_company=True,
        domain="[('sedar_tugboat_id', '=', parent.tugboat_id), ('sedar_hours_from_id', '=', False)]",
    )
    engine_status = fields.Selection(
        [("operated", "Operated"), ("no_operation", "No Operation"), ("standby", "Standby")],
        default="operated", required=True,
        help="Operated engines ran for the whole watch; No Operation and Standby engines ran for none of it.",
    )
    hours_run = fields.Float(
        string="Hours Run", compute="_compute_hours_run", store=True,
        help="The length of the watch for an operated engine, to a tenth of an hour; zero otherwise.",
    )
    rpm = fields.Float(string="RPM")
    oil_pressure = fields.Float(string="Oil Pressure (bar)")
    water_temp = fields.Float(string="Water Temp (°C)")
    fuel_rob_start = fields.Float(string="Fuel R.O.B. Start (L)")
    fuel_rob_stop = fields.Float(string="Fuel R.O.B. Stop (L)")
    fuel_consumed = fields.Float(
        string="Fuel Consumed (L)", compute="_compute_fuel_consumed", store=True,
        help="Fuel remaining on board at the start less at the stop, for an operated engine.",
    )
    reading_id = fields.Many2one(
        "sedar.equipment.running.hour.reading", string="Reading", readonly=True, copy=False, ondelete="restrict"
    )

    _one_line_per_engine = models.Constraint(
        "unique(report_id, equipment_id)", "An engine can appear only once per report."
    )

    @api.depends("engine_status", "report_id.watch_start", "report_id.watch_stop")
    def _compute_hours_run(self):
        for line in self:
            report = line.report_id
            line.hours_run = (
                round((report.watch_stop - report.watch_start) % 24, 1) if line.engine_status == "operated" else 0.0
            )

    @api.depends("engine_status", "fuel_rob_start", "fuel_rob_stop")
    def _compute_fuel_consumed(self):
        for line in self:
            line.fuel_consumed = (
                max(line.fuel_rob_start - line.fuel_rob_stop, 0.0) if line.engine_status == "operated" else 0.0
            )

    @api.constrains("equipment_id", "report_id", *MEASUREMENTS)
    def _check_line(self):
        for line in self:
            if any(line[name] < 0 for name in MEASUREMENTS):
                raise ValidationError(_("RPM, pressure, temperature and fuel quantities cannot be negative."))
            engine = line.equipment_id
            if engine.sedar_tugboat_id != line.report_id.tugboat_id or engine.sedar_hours_from_id:
                raise ValidationError(_(
                    "%(engine)s must be an engine of %(tug)s that keeps its own running hours.",
                    engine=engine.display_name, tug=line.report_id.tugboat_id.name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(
            self.env["sedar.daily.engine.report"].browse(vals.get("report_id")).state != "draft"
            for vals in vals_list
        ):
            raise AccessError(_("A submitted or posted report cannot be edited."))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda line: line.state != "draft") and not self.env.su:
            raise AccessError(_("A submitted or posted report cannot be edited."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if self.filtered(lambda line: line.state == "posted") or (
            not self.env.su and self.filtered(lambda line: line.state != "draft")
        ):
            raise UserError(_("A submitted or posted report cannot be edited."))

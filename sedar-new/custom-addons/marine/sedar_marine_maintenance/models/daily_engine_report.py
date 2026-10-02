from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


MEASUREMENTS = ("fuel_consumed", "rpm", "oil_pressure", "water_temp", "fuel_rob", "lube_oil_refill")


class SedarDailyEngineReport(models.Model):
    """Daily Engine Monitoring Report: the chief engineer's daily hours; posting adds them to each engine's meter."""

    _name = "sedar.daily.engine.report"
    _description = "Daily Engine Monitoring Report"
    _order = "report_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    tugboat_id = fields.Many2one(
        "sedar.tugboat", string="Tugboat", required=True, index=True, ondelete="restrict",
    )
    company_id = fields.Many2one(related="tugboat_id.company_id", store=True, index=True)
    report_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted")], default="draft", required=True, readonly=True, copy=False
    )
    prepared_by_id = fields.Many2one(
        "res.users", string="Prepared By", readonly=True, copy=False,
        default=lambda self: self.env.user, ondelete="restrict",
    )
    posted_at = fields.Datetime(readonly=True, copy=False)
    posted_by_id = fields.Many2one(
        "res.users", string="Noted By", readonly=True, copy=False, ondelete="restrict",
        help="The user who posted the report, as the Chief Engineer's note on the paper form.",
    )
    rob_diesel = fields.Float(string="D.O. R.O.B. (L)")
    rob_lube_40 = fields.Float(string="L.O. 40 R.O.B. (L)")
    rob_lube_15w40 = fields.Float(string="L.O. 15W-40 R.O.B. (L)")
    rob_hydraulic = fields.Float(string="Hydraulic Oil R.O.B. (L)")
    rob_fresh_water = fields.Float(string="Fresh Water R.O.B.")
    remarks = fields.Text()
    line_ids = fields.One2many("sedar.daily.engine.report.line", "report_id", string="Engines", copy=True)

    @api.depends("tugboat_id.name", "report_date")
    def _compute_name(self):
        for report in self:
            report.name = _("%(tug)s — %(date)s", tug=report.tugboat_id.name or "", date=report.report_date or "")

    @api.constrains("report_date", "tugboat_id")
    def _check_report_date(self):
        today = fields.Date.context_today(self)
        for report in self:
            if report.report_date > today:
                raise ValidationError(_("A report cannot be dated in the future."))
            if self.search_count([
                ("tugboat_id", "=", report.tugboat_id.id),
                ("report_date", "=", report.report_date),
                ("id", "!=", report.id),
            ]):
                raise ValidationError(_("This tugboat already has a Daily Engine Monitoring Report for that date."))

    @api.constrains("rob_diesel", "rob_lube_40", "rob_lube_15w40", "rob_hydraulic", "rob_fresh_water")
    def _check_rob(self):
        for report in self:
            if min(report.rob_diesel, report.rob_lube_40, report.rob_lube_15w40,
                   report.rob_hydraulic, report.rob_fresh_water) < 0:
                raise ValidationError(_("Remaining on board cannot be negative."))

    @api.onchange("tugboat_id")
    def _onchange_tugboat_id(self):
        engines = self.env["maintenance.equipment"].search([
            ("sedar_tugboat_id", "=", self.tugboat_id.id),
            ("sedar_hours_from_id", "=", False),
            ("sedar_running_hour_reading_ids", "!=", False),
        ]) if self.tugboat_id else self.env["maintenance.equipment"]
        self.line_ids = [Command.clear()] + [Command.create({"equipment_id": engine.id}) for engine in engines]

    def action_post(self):
        for report in self:
            if report.state == "posted":
                continue
            lines = report.line_ids
            if not lines:
                raise UserError(_("Add at least one engine before posting."))
            equipment = lines.equipment_id
            self.env.cr.execute("SELECT id FROM maintenance_equipment WHERE id IN %s FOR UPDATE", [tuple(equipment.ids)])
            equipment.invalidate_recordset(["sedar_current_running_hours"])
            for line in lines.filtered("hours_run"):
                line.reading_id = self.env["sedar.equipment.running.hour.reading"].create({
                    "equipment_id": line.equipment_id.id,
                    "running_hours": line.equipment_id.sedar_current_running_hours + line.hours_run,
                    "notes": _("Daily Engine Monitoring Report %s", report.name),
                })
            report.write({
                "state": "posted", "posted_at": fields.Datetime.now(), "posted_by_id": self.env.user.id,
            })
        return True

    def write(self, vals):
        if self.filtered(lambda report: report.state == "posted") and not self.env.su:
            raise AccessError(_("A posted report cannot be edited."))
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
    hours_run = fields.Float(string="Hours Run", help="Hours the engine ran during the report day.")
    fuel_consumed = fields.Float(string="Fuel Consumed (L)")
    time_start = fields.Float(string="Started", help="Time of day the engine was started.")
    time_stop = fields.Float(string="Stopped", help="Time of day the engine was stopped.")
    rpm = fields.Float(string="RPM")
    oil_pressure = fields.Float(string="Oil Pressure")
    water_temp = fields.Float(string="Water Temp (°C)")
    fuel_rob = fields.Float(string="Service Tank R.O.B. (L)", help="Fuel remaining in the service tank.")
    lube_oil_refill = fields.Float(string="Lube Oil Refill (L)")
    remarks = fields.Char()
    reading_id = fields.Many2one(
        "sedar.equipment.running.hour.reading", string="Reading", readonly=True, copy=False, ondelete="restrict"
    )

    _one_line_per_engine = models.Constraint(
        "unique(report_id, equipment_id)", "An engine can appear only once per report."
    )

    @api.onchange("time_start", "time_stop")
    def _onchange_times(self):
        if self.time_start != self.time_stop:
            self.hours_run = (self.time_stop - self.time_start) % 24

    @api.constrains("hours_run", "equipment_id", "report_id", "time_start", "time_stop", *MEASUREMENTS)
    def _check_line(self):
        for line in self:
            if not 0 <= line.hours_run <= 24:
                raise ValidationError(_("Hours run in one day must be between 0 and 24."))
            if not (0 <= line.time_start < 24 and 0 <= line.time_stop < 24):
                raise ValidationError(_("Start and stop times must be within one day."))
            if any(line[name] < 0 for name in MEASUREMENTS):
                raise ValidationError(_("Fuel, RPM, pressure, temperature and oil quantities cannot be negative."))
            engine = line.equipment_id
            if engine.sedar_tugboat_id != line.report_id.tugboat_id or engine.sedar_hours_from_id:
                raise ValidationError(_(
                    "%(engine)s must be an engine of %(tug)s that keeps its own running hours.",
                    engine=engine.display_name, tug=line.report_id.tugboat_id.name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(
            self.env["sedar.daily.engine.report"].browse(vals.get("report_id")).state == "posted"
            for vals in vals_list
        ):
            raise AccessError(_("A posted report cannot be edited."))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda line: line.state == "posted") and not self.env.su:
            raise AccessError(_("A posted report cannot be edited."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if self.filtered(lambda line: line.state == "posted"):
            raise UserError(_("A posted report cannot be edited."))

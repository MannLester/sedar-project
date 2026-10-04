from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from .daily_engine_report import MANAGER_GROUP

LINE_FIELDS = (
    "equipment_id", "engine_status", "rpm", "oil_pressure", "water_temp", "fuel_rob_start", "fuel_rob_stop",
)
HISTORY_LIMIT = 60


class SedarDailyEngineReportEngineRoom(models.Model):
    """What the Engine Room page (static/engine_room) reads and writes; every rule stays in the report model."""

    _inherit = "sedar.daily.engine.report"

    @api.model
    def _sedar_engine_room_snapshot(self):
        """Everything the page needs to work without a connection."""
        return {
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "user": self.env.user.name,
            "can_approve": self.env.user.has_group(MANAGER_GROUP),
            "tugs": [self._sedar_engine_room_tug(tug) for tug in self.env["sedar.tugboat"].search([])],
        }

    @api.model
    def _sedar_engine_room_tug(self, tug):
        engines = self.env["maintenance.equipment"].search([
            ("sedar_tugboat_id", "=", tug.id),
            ("sedar_hours_from_id", "=", False),
            ("sedar_running_hour_reading_ids", "!=", False),
        ]).sorted(lambda engine: (engine.sedar_system != "propulsion", engine.name))
        tasks = self.env["sedar.pm.task"].search([("tugboat_id", "=", tug.id)])
        reports = self.search([("tugboat_id", "=", tug.id)], limit=HISTORY_LIMIT)
        return {
            "id": tug.id,
            "name": tug.name,
            "engines": [self._sedar_engine_room_engine(engine, tasks) for engine in engines],
            "reports": [self._sedar_engine_room_report(report) for report in reports],
            "open_pm_tasks": len(tasks.filtered(lambda task: task.state in ("approaching", "due", "overdue"))),
        }

    @api.model
    def _sedar_engine_room_engine(self, engine, tasks):
        due = tasks.filtered(lambda task: (task.equipment_id.sedar_hours_from_id or task.equipment_id) == engine)
        next_task = min(due, key=lambda task: task.remaining_hours, default=None)
        last_line = self.env["sedar.daily.engine.report.line"].search([
            ("equipment_id", "=", engine.id), ("report_id.state", "=", "posted"),
        ], order="id desc", limit=1)
        return {
            "id": engine.id,
            "name": engine.name,
            "kind": "main" if engine.sedar_system == "propulsion" else "auxiliary",
            "hours": engine.sedar_current_running_hours,
            "last_fuel_rob": last_line.fuel_rob_stop,
            "next_pm": next_task and {
                "name": next_task.name,
                "interval_hours": next_task.interval_hours,
                "remaining_hours": next_task.remaining_hours,
            },
        }

    @api.model
    def _sedar_engine_room_report(self, report):
        return {
            "id": report.id,
            "log_id": report.log_key or "r%d" % report.id,
            "date": fields.Date.to_string(report.report_date),
            "watch_start": report.watch_start,
            "watch_stop": report.watch_stop,
            "state": report.state,
            "return_reason": report.return_reason or "",
            "prepared_by": report.prepared_by_id.name or "",
            "approved_by": report.posted_by_id.name or "",
            "hours": max(report.line_ids.mapped("hours_run"), default=0.0),
            "fuel": sum(report.line_ids.mapped("fuel_consumed")),
            "lines": [
                {
                    **{name: line[name] for name in LINE_FIELDS if name != "equipment_id"},
                    "equipment_id": line.equipment_id.id,
                    "hours_run": line.hours_run,
                    "fuel_consumed": line.fuel_consumed,
                    "meter_previous": (
                        line.reading_id.running_hours - line.hours_run
                        if line.reading_id else line.equipment_id.sedar_current_running_hours
                    ),
                }
                for line in report.line_ids
            ],
        }

    @api.model
    def _sedar_find_log(self, log_id):
        if log_id.startswith("r") and log_id[1:].isdigit():
            return self.browse(int(log_id[1:])).exists()
        return self.search([("log_key", "=", log_id)], limit=1)

    @api.model
    def _sedar_save_log(self, item, submit=False):
        """Create or replace the draft watch log the page uploaded, optionally submitting it."""
        tug = self.env["sedar.tugboat"].browse(item["tugboat_id"]).exists()
        if not tug:
            raise UserError(_("The tugboat no longer exists."))
        log_id = str(item["log_id"])
        report = self._sedar_find_log(log_id)
        if report.state in ("submitted", "posted"):
            raise UserError(_("%(report)s is already %(state)s.", report=report.name, state=report.state))
        values = {
            "watch_start": item["watch_start"],
            "watch_stop": item["watch_stop"],
            "line_ids": [Command.clear()] + [
                Command.create({name: line[name] for name in LINE_FIELDS if name in line}) for line in item["lines"]
            ],
        }
        if report:
            report.write(values)
        else:
            report = self.create({
                "tugboat_id": tug.id, "report_date": fields.Date.to_date(item["report_date"]),
                "log_key": log_id, **values,
            })
        if submit:
            report.action_submit()
        return report

    @api.model
    def _sedar_review(self, item):
        """The Chief Engineer's online actions: approve, saving an entered log first, or return a submitted one."""
        self._check_can_approve()
        if "lines" in item:
            report = self._sedar_save_log(item)
        else:
            report = self._sedar_find_log(str(item["log_id"]))
            if not report:
                raise UserError(_("The report no longer exists."))
        if item["action"] == "approve":
            report.action_post()
        elif item["action"] == "return":
            report.action_return(item.get("reason"))
        else:
            raise UserError(_("Unknown action."))
        return self._sedar_engine_room_report(report)

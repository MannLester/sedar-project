import time
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEngineRoom(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Engine Room Tug",
            "registration_number": "ER-TUG",
            "tug_class_id": cls.env["sedar.tug.class"].create({"name": "Engine Room Class"}).id,
            "availability_status": "available",
        })
        category = cls.env["maintenance.equipment.category"].create({"name": "Engine Room Category"})
        team = cls.env["maintenance.team"].create({"name": "Engine Room Team"})
        cls.engines = cls.env["maintenance.equipment"]
        for name, system in (("Engine Room Main Engine", "propulsion"), ("Engine Room Generator", "electrical")):
            engine = cls.env["maintenance.equipment"].create({
                "name": name, "category_id": category.id, "maintenance_team_id": team.id,
                "sedar_tugboat_id": cls.tug.id, "sedar_system": system,
            })
            cls.env["sedar.equipment.running.hour.reading"].create({
                "equipment_id": engine.id, "running_hours": 100,
                "reading_at": fields.Datetime.now() - timedelta(days=1),
            })
            cls.engines |= engine
        cls.main, cls.generator = cls.engines
        cls.env["sedar.pm.task"].create({"name": "250-hour check", "equipment_id": cls.main.id, "interval_hours": 250})
        cls.duty = cls._user("duty", "group_marine_maintenance_user")
        cls.chief = cls._user("chief", "group_marine_maintenance_manager")
        cls.today = str(fields.Date.context_today(cls.env["sedar.daily.engine.report"]))
        cls.Report = cls.env["sedar.daily.engine.report"]

    @classmethod
    def _user(cls, login, group):
        return cls.env["res.users"].create({
            "name": f"Engine Room {login}",
            "login": f"engine.room.{login}@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref(f"sedar_marine_maintenance.{group}").id,
            ])],
        })

    def _item(self, log_id="log-1", **extra):
        return {
            "log_id": log_id,
            "tugboat_id": self.tug.id,
            "report_date": self.today,
            "watch_start": 6.0,
            "watch_stop": 12.5,
            "lines": [
                {"equipment_id": self.main.id, "engine_status": "operated", "rpm": 720, "oil_pressure": 4.2,
                 "water_temp": 82, "fuel_rob_start": 18450, "fuel_rob_stop": 18150},
                {"equipment_id": self.generator.id, "engine_status": "standby", "fuel_rob_start": 900,
                 "fuel_rob_stop": 900},
            ],
            **extra,
        }

    def _submit(self, **extra):
        return self.Report.with_user(self.duty)._sedar_save_log(self._item(**extra), submit=True)

    def test_snapshot_lists_engines_with_kind_and_next_pm(self):
        snapshot = self.Report.with_user(self.chief)._sedar_engine_room_snapshot()
        self.assertTrue(snapshot["can_approve"])
        tug = next(tug for tug in snapshot["tugs"] if tug["id"] == self.tug.id)
        engines = {engine["id"]: engine for engine in tug["engines"]}
        self.assertEqual(engines[self.main.id]["kind"], "main")
        self.assertEqual(engines[self.generator.id]["kind"], "auxiliary")
        self.assertEqual(engines[self.main.id]["hours"], 100)
        self.assertEqual(engines[self.main.id]["next_pm"]["remaining_hours"], 150)
        self.assertIsNone(engines[self.generator.id]["next_pm"])
        self.assertEqual(tug["open_pm_tasks"], 0)

    def test_watch_log_hours_and_fuel_follow_the_watch_window(self):
        report = self._submit()
        main_line, generator_line = report.line_ids
        self.assertEqual((main_line.hours_run, main_line.fuel_consumed), (6.5, 300))
        self.assertEqual((generator_line.hours_run, generator_line.fuel_consumed), (0, 0))
        self.assertEqual(report.name, "Engine Room Tug — %s 06:00–12:30" % self.today)

    def test_several_watches_in_one_day_each_post_their_own_hours(self):
        first = self._submit()
        second = self._submit(log_id="log-2", watch_start=14.0, watch_stop=16.0)
        with self.assertRaises(ValidationError):
            self._submit(log_id="log-3", watch_start=14.0, watch_stop=15.0)
        first.with_user(self.chief).action_post()
        time.sleep(1.1)
        second.with_user(self.chief).action_post()
        self.assertEqual(self.main.sedar_current_running_hours, 108.5)

    def test_duty_engineer_submits_and_cannot_approve_or_edit(self):
        report = self._submit()
        self.assertEqual(report.state, "submitted")
        self.assertEqual(self.main.sedar_current_running_hours, 100)
        with self.assertRaises(AccessError):
            report.action_post()
        with self.assertRaises(AccessError):
            report.watch_stop = 13.0
        with self.assertRaises(UserError):
            self._submit()

    def test_operated_engine_needs_a_watch_that_runs(self):
        with self.assertRaises(UserError):
            self._submit(watch_stop=6.0)

    def test_chief_returns_with_reason_then_crew_resubmits_the_same_log(self):
        report = self._submit()
        with self.assertRaises(AccessError):
            report.action_return("no")
        with self.assertRaises(UserError):
            report.with_user(self.chief).action_return(" ")
        report.with_user(self.chief).action_return("Generator hours missing")
        self.assertEqual((report.state, report.return_reason), ("draft", "Generator hours missing"))

        item = self._item(watch_stop=14.0)
        item["lines"][1]["engine_status"] = "operated"
        resubmitted = self.Report.with_user(self.duty)._sedar_save_log(item, submit=True)
        self.assertEqual((resubmitted, resubmitted.state, resubmitted.return_reason), (report, "submitted", False))
        self.assertEqual(report.line_ids.mapped("hours_run"), [8.0, 8.0])

    def test_chief_approval_adds_hours_and_saves_an_unsubmitted_log(self):
        with self.assertRaises(AccessError):
            self.Report.with_user(self.duty)._sedar_review({**self._item(), "action": "approve"})
        result = self.Report.with_user(self.chief)._sedar_review({**self._item(), "action": "approve"})
        self.assertEqual((result["state"], result["approved_by"]), ("posted", self.chief.name))
        self.assertEqual(self.main.sedar_current_running_hours, 106.5)
        self.assertEqual(self.generator.sedar_current_running_hours, 100)
        main_line = next(line for line in result["lines"] if line["equipment_id"] == self.main.id)
        self.assertEqual(main_line["meter_previous"], 100)

    def test_chief_approves_a_submitted_report_by_log_id(self):
        self._submit()
        result = self.Report.with_user(self.chief)._sedar_review({"log_id": "log-1", "action": "approve"})
        self.assertEqual(result["state"], "posted")
        self.assertEqual(self.main.sedar_current_running_hours, 106.5)
        with self.assertRaises(UserError):
            self.Report.with_user(self.chief)._sedar_review({"log_id": "log-1", "action": "lunch"})
        snapshot = self.Report.with_user(self.duty)._sedar_engine_room_snapshot()
        tug = next(tug for tug in snapshot["tugs"] if tug["id"] == self.tug.id)
        engines = {engine["id"]: engine for engine in tug["engines"]}
        self.assertEqual(engines[self.main.id]["last_fuel_rob"], 18150)

    def test_old_reports_are_found_by_their_database_id(self):
        report = self.Report.create({"tugboat_id": self.tug.id, "watch_start": 1.0, "watch_stop": 2.0})
        self.assertEqual(self.Report._sedar_find_log("r%d" % report.id), report)
        self.assertEqual(self.Report._sedar_engine_room_report(report)["log_id"], "r%d" % report.id)

    def test_negative_measurements_are_refused(self):
        item = self._item()
        item["lines"][0]["rpm"] = -1
        with self.assertRaises(ValidationError):
            self.Report.with_user(self.duty)._sedar_save_log(item)

    def test_submission_waits_in_the_offline_queue_until_synced(self):
        log = self.env["sedar.ship.log.entry"].with_user(self.duty)
        entry = {"client_id": "engine-room-1", "kind": "report", **self._item()}
        self.assertTrue(log._sedar_sync([entry])[0]["ok"])
        self.assertEqual(
            log._sedar_sync([entry])[0]["message"], "Report Engine Room Tug — %s 06:00–12:30 submitted." % self.today
        )
        self.assertEqual(self.Report.search_count([("tugboat_id", "=", self.tug.id)]), 1)

    def test_duty_cannot_forge_the_workflow_or_delete_a_submitted_log(self):
        report = self.Report.with_user(self.duty).create({"tugboat_id": self.tug.id, "watch_start": 1.0, "watch_stop": 2.0})
        with self.assertRaises(AccessError):
            report.write({"state": "posted", "posted_by_id": self.chief.id})
        with self.assertRaises(AccessError):
            report.write({"log_key": "someone-elses"})
        with self.assertRaises(AccessError):
            self.Report.with_user(self.duty).create({"tugboat_id": self.tug.id, "watch_start": 3.0, "state": "posted"})
        submitted = self._submit()
        with self.assertRaises(UserError):
            submitted.unlink()
        report.line_ids = [(0, 0, {"equipment_id": self.main.id})]
        with self.assertRaises(AccessError):
            report.line_ids.write({"reading_id": 1})

    def test_watches_of_one_tugboat_cannot_overlap(self):
        self._submit()
        for start, stop in ((6.5, 9.0), (5.0, 7.0), (7.0, 11.0)):
            with self.assertRaises(ValidationError):
                self._submit(log_id=f"clash-{start}", watch_start=start, watch_stop=stop)
        self._submit(log_id="after", watch_start=12.5, watch_stop=14.0)

    def test_a_watch_without_a_start_is_not_accepted(self):
        with self.assertRaises(TypeError):
            self.Report.with_user(self.duty)._sedar_save_log({**self._item(), "watch_start": None})

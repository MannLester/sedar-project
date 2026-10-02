from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMarineMaintenance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Maintenance Client"})
        cls.port = cls.env["sedar.marine.port"].create({"name": "Maintenance Port", "code": "MNT"})
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Maintenance Assist",
            "code": "MNT-A",
            "pricing_basis": "per_service",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Maintenance Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Maintenance Test Tug",
            "registration_number": "MNT-TUG",
            "tug_class_id": cls.tug_class.id,
            "availability_status": "available",
        })
        cls.team = cls.env["maintenance.team"].create({"name": "Maintenance Test Team"})
        cls.category = cls.env["maintenance.equipment.category"].create({"name": "Maintenance Test Category"})
        cls.equipment = cls.env["maintenance.equipment"].create({
            "name": "Maintenance Test Main Engine",
            "category_id": cls.category.id,
            "maintenance_team_id": cls.team.id,
            "sedar_tugboat_id": cls.tug.id,
            "sedar_system": "propulsion",
            "sedar_criticality": "critical",
        })
        cls.manager = cls.env["res.users"].create({
            "name": "Maintenance Test Manager",
            "login": "maintenance.manager@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_marine_maintenance.group_marine_maintenance_manager").id,
            ])],
        })
        cls.maintenance_user = cls.env["res.users"].create({
            "name": "Maintenance Test User",
            "login": "maintenance.user@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_marine_maintenance.group_marine_maintenance_user").id,
            ])],
        })
        cls.done_stage = cls.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        if not cls.done_stage:
            cls.done_stage = cls.env["maintenance.stage"].create({
                "name": "Maintenance Test Done",
                "done": True,
            })
        cls.open_stage = cls.env["maintenance.stage"].create({
            "name": "Maintenance Test In Progress",
            "done": False,
        })

    def _new_metered_equipment(self, name="Metered Test Engine", technician=None):
        return self.env["maintenance.equipment"].create({
            "name": name,
            "category_id": self.category.id,
            "maintenance_team_id": self.team.id,
            "technician_user_id": technician.id if technician else False,
            "sedar_tugboat_id": self.tug.id,
            "sedar_system": "propulsion",
            "sedar_criticality": "critical",
        })

    def _reading(self, equipment, hours, reading_at, user=None, **extra):
        return self.env["sedar.equipment.running.hour.reading"].with_user(
            user or self.maintenance_user
        ).create({
            "equipment_id": equipment.id,
            "running_hours": hours,
            "reading_at": reading_at,
            **extra,
        })

    def _make_order_with_tug(self):
        order = self.env["sedar.marine.service.order"].create({
            "client_id": self.partner.id,
            "assisted_vessel_name": "MV Maintenance Test",
            "service_type_id": self.service.id,
            "number_of_tugs": 1,
            "scope_of_work": "Maintenance readiness test.",
            "port_id": self.port.id,
            "requested_start": datetime(2026, 9, 5, 8, 0, 0),
            "estimated_duration_hours": 2,
            "state": "planning",
            "inventory_ready": True,
        })
        self.env["sedar.tug.assignment"].create({
            "order_id": order.id,
            "tugboat_id": self.tug.id,
        })
        return order

    def test_blocking_work_order_blocks_service_order_readiness_and_release_restores(self):
        order = self._make_order_with_tug()
        work_order = self.env["maintenance.request"].create({
            "name": "Blocking Test Defect",
            "maintenance_type": "corrective",
            "equipment_id": self.equipment.id,
            "sedar_work_order_type": "defect",
            "sedar_defect_source": "Pre-departure inspection",
            "sedar_availability_impact": "blocking",
        })

        self.assertTrue(work_order.sedar_blocks_tug_readiness)
        self.assertEqual(self.tug.availability_status, "maintenance")
        self.assertEqual(order.readiness_status, "blocked_tug")

        with self.assertRaises(UserError):
            work_order.with_user(self.manager).action_sedar_release_tug()

        work_order.sedar_closure_note = "Leak repaired and verified during harbor run."
        work_order.with_user(self.manager).action_sedar_release_tug()
        self.assertFalse(work_order.sedar_blocks_tug_readiness)
        self.assertEqual(self.tug.availability_status, "available")

    def test_planned_drydock_blocks_only_overlapping_jobs_and_in_progress_blocks_current_tug(self):
        work_order = self.env["maintenance.request"].create({
            "name": "Drydock Related Defect",
            "maintenance_type": "corrective",
            "equipment_id": self.equipment.id,
            "sedar_work_order_type": "defect",
            "sedar_defect_source": "Engineering inspection",
            "sedar_availability_impact": "blocking",
        })
        plan = self.env["sedar.drydock.plan"].create({
            "name": "Maintenance Test Dry Dock",
            "tugboat_id": self.tug.id,
            "planned_start": datetime(2026, 9, 10, 8, 0, 0),
            "planned_end": datetime(2026, 9, 20, 17, 0, 0),
            "yard_name": "Test Yard",
            "scope_summary": "Demo planned dry dock.",
            "state": "planned",
        })
        self.assertTrue(plan.sedar_blocks_window(
            datetime(2026, 9, 12, 8, 0, 0), datetime(2026, 9, 12, 10, 0, 0)
        ))
        self.assertFalse(plan.sedar_blocks_window(
            datetime(2026, 9, 5, 8, 0, 0), datetime(2026, 9, 5, 10, 0, 0)
        ))
        self.assertEqual(self.tug.availability_status, "maintenance")

        work_order.sedar_closure_note = "Corrective work verified."
        work_order.with_user(self.manager).action_sedar_release_tug()
        self.assertEqual(self.tug.availability_status, "available")

        with self.assertRaises(UserError):
            plan.with_user(self.manager).action_complete()

        plan.release_note = "Dry dock sea trial completed."
        plan.with_user(self.manager).action_start()
        self.assertEqual(self.tug.availability_status, "maintenance")
        plan.with_user(self.manager).action_complete()
        self.assertEqual(self.tug.availability_status, "available")

    def test_drydock_dates_are_validated(self):
        with self.assertRaises(ValidationError):
            self.env["sedar.drydock.plan"].create({
                "name": "Invalid Dry Dock",
                "tugboat_id": self.tug.id,
                "planned_start": datetime(2026, 9, 20, 17, 0, 0),
                "planned_end": datetime(2026, 9, 10, 8, 0, 0),
                "yard_name": "Test Yard",
                "scope_summary": "Invalid dates.",
            })

    def test_running_hour_readings_are_immutable_and_validate_both_neighbors(self):
        equipment = self._new_metered_equipment()
        now = fields.Datetime.now()
        first = self._reading(equipment, 100, now - timedelta(days=3))
        latest = self._reading(equipment, 200, now - timedelta(days=1))
        middle = self._reading(equipment, 150, now - timedelta(days=2))

        self.assertEqual(equipment.sedar_current_running_hour_reading_id, latest)
        self.assertEqual(equipment.sedar_current_running_hours, 200)
        self.assertEqual(middle.recorded_by_id, self.maintenance_user)
        self.assertIn(equipment.name, latest.display_name)
        self.assertIn("200.00 h", latest.display_name)

        with self.assertRaises(ValidationError):
            self._reading(equipment, 210, now - timedelta(days=2, hours=1))
        with self.assertRaises(ValidationError):
            self._reading(equipment, 199, now - timedelta(days=1))
        with self.assertRaises(ValidationError):
            self._reading(equipment, 210, now + timedelta(hours=1))
        with self.assertRaises(AccessError):
            latest.with_user(self.manager).with_context(
                sedar_allow_reading_audit_write=True
            ).write({"running_hours": 201})
        with self.assertRaises(AccessError):
            self._reading(
                equipment,
                210,
                now - timedelta(hours=12),
                superseded_by_id=self.manager.id,
            )
        with self.assertRaises(UserError):
            latest.with_user(self.manager).unlink()

        with self.assertRaises(AccessError):
            self._reading(
                equipment,
                205,
                latest.reading_at,
                user=self.maintenance_user,
                supersedes_reading_id=latest.id,
                correction_reason="Recorder transposed the final digit.",
            )

        correction = self._reading(
            equipment,
            205,
            latest.reading_at,
            user=self.manager,
            supersedes_reading_id=latest.id,
            correction_reason="Verified against the signed engine-room log.",
        )
        self.assertEqual(latest.state, "superseded")
        self.assertEqual(latest.superseded_by_id, self.manager)
        self.assertEqual(correction.state, "valid")
        self.assertEqual(equipment.sedar_current_running_hour_reading_id, correction)
        self.assertEqual(equipment.sedar_current_running_hours, 205)
        self.assertEqual(first.state, "valid")

    def _task(self, equipment, interval=300, **extra):
        return self.env["sedar.pm.task"].with_user(self.maintenance_user).create({
            "name": f"{interval}-hour check",
            "equipment_id": equipment.id,
            "interval_hours": interval,
            **extra,
        })

    def _complete(self, task, user=None, **extra):
        return self.env["sedar.pm.task.completion"].with_user(user or self.maintenance_user).create({
            "task_id": task.id, **extra,
        })

    def test_checkpoints_are_fixed_multiples_even_when_done_late(self):
        equipment = self._new_metered_equipment(technician=self.maintenance_user)
        task = self._task(equipment)
        now = fields.Datetime.now()
        self.assertEqual((task.state, task.next_checkpoint_hours), ("not_due", 300))

        self._reading(equipment, 250, now - timedelta(days=4))
        self.assertEqual(task.state, "approaching")
        with self.assertRaises(UserError):
            self._complete(self._task(equipment, 600))
        self._reading(equipment, 300, now - timedelta(days=3))
        self.assertEqual(task.state, "due")
        self._reading(equipment, 301, now - timedelta(days=2))
        self.assertEqual(task.state, "overdue")

        self._reading(equipment, 308, now - timedelta(days=1))
        done = self._complete(task, remarks="Visual inspection OK")
        self.assertEqual((done.checkpoint_hours, done.running_hours), (300, 308))
        self.assertEqual((task.next_checkpoint_hours, task.state), (600, "not_due"))
        with self.assertRaises(UserError):
            self._complete(task)
        with self.assertRaises(AccessError):
            done.write({"remarks": "edited"})
        with self.assertRaises(UserError):
            done.with_user(self.manager).unlink()
        with self.assertRaises(AccessError):
            self._complete(task, checkpoint_hours=0)

        self._reading(equipment, 560, now - timedelta(hours=3))
        self.assertEqual(task.state, "approaching")
        self._reading(equipment, 605, now - timedelta(hours=2))
        self.assertEqual(task.state, "overdue")
        self._complete(task)
        self.assertEqual((task.next_checkpoint_hours, task.state), (900, "not_due"))

    def test_missed_checkpoint_stays_overdue_until_done(self):
        equipment = self._new_metered_equipment()
        task = self._task(equipment, 300)
        self._reading(equipment, 650, fields.Datetime.now() - timedelta(hours=1))
        self.assertEqual((task.next_checkpoint_hours, task.state), (300, "overdue"))
        self._complete(task)
        self.assertEqual((task.next_checkpoint_hours, task.state), (600, "overdue"))
        self._complete(task)
        self.assertEqual((task.next_checkpoint_hours, task.state), (900, "not_due"))

    def test_components_follow_engine_hours_and_equipment_shows_worst_status(self):
        engine = self._new_metered_equipment(name="Shared Hours Engine")
        pump = self._new_metered_equipment(name="Shared Hours Pump")
        pump.sedar_hours_from_id = engine
        fast = self._task(pump, 100)
        slow = self._task(pump, 1000)
        self.assertEqual(pump.sedar_service_due_state, "not_due")

        self._reading(engine, 120, fields.Datetime.now() - timedelta(hours=1))
        self.assertEqual(pump.sedar_current_running_hours, 120)
        self.assertEqual((fast.state, slow.state), ("overdue", "not_due"))
        self.assertEqual(pump.sedar_service_due_state, "overdue")
        self.assertEqual(pump.sedar_next_service_hours, 100)
        with self.assertRaises(ValidationError):
            self._reading(pump, 130, fields.Datetime.now())
        with self.assertRaises(ValidationError):
            engine.sedar_hours_from_id = pump

    def test_due_checkpoint_creates_one_activity_and_completion_closes_it(self):
        self.env.company.sedar_maintenance_fallback_user_id = self.manager
        equipment = self._new_metered_equipment()
        task = self._task(equipment, 100)
        self.assertEqual(task.alert_assignment_state, "not_required")
        now = fields.Datetime.now()
        self._reading(equipment, 100, now - timedelta(hours=2))
        task._sedar_reconcile_alert()
        activities = task.sedar_open_alerts()

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.manager)
        self.assertEqual(task.alert_assignment_state, "assigned")
        self.assertEqual(task.alerted_cycle_key, task.cycle_key)

        self._complete(task)
        self.assertFalse(task.sedar_open_alerts())
        self.assertEqual(task.state, "not_due")

    def test_manager_correction_closes_stale_alert(self):
        equipment = self._new_metered_equipment(technician=self.manager)
        task = self._task(equipment, 100)
        reading = self._reading(equipment, 100, fields.Datetime.now() - timedelta(hours=2))
        self.assertEqual(len(task.sedar_open_alerts()), 1)
        self._reading(
            equipment, 90, reading.reading_at, user=self.manager,
            supersedes_reading_id=reading.id, correction_reason="Meter photo shows 90.",
        )
        self.assertEqual(task.state, "approaching")
        self.assertFalse(task.sedar_open_alerts())

    def test_daily_engine_report_adds_hours_and_locks(self):
        engine = self._new_metered_equipment(name="Report Engine")
        self._reading(engine, 100, fields.Datetime.now() - timedelta(days=2))
        task = self._task(engine, 110)
        Report = self.env["sedar.daily.engine.report"].with_user(self.maintenance_user)
        report = Report.create({
            "tugboat_id": self.tug.id,
            "line_ids": [(0, 0, {"equipment_id": engine.id, "hours_run": 12.5, "fuel_consumed": 410})],
        })
        with self.assertRaises(ValidationError):
            Report.create({"tugboat_id": self.tug.id})
        with self.assertRaises(ValidationError):
            report.line_ids.hours_run = 25

        report.action_post()
        self.assertEqual(report.state, "posted")
        self.assertEqual(engine.sedar_current_running_hours, 112.5)
        self.assertEqual(report.line_ids.reading_id.running_hours, 112.5)
        self.assertEqual(task.state, "overdue")
        with self.assertRaises(AccessError):
            report.remarks = "late edit"
        with self.assertRaises(AccessError):
            report.line_ids.hours_run = 1
        with self.assertRaises(UserError):
            report.unlink()

    def _dry_dock(self, **extra):
        return self.env["sedar.drydock.plan"].create({
            "name": "Test Dry Dock",
            "tugboat_id": self.tug.id,
            "planned_start": datetime(2026, 9, 1, 8, 0, 0),
            "planned_end": datetime(2026, 9, 20, 8, 0, 0),
            "yard_name": "Test Yard",
            "scope_summary": "Hull and propulsion overhaul.",
            **extra,
        })

    def _finish_dry_dock(self, plan):
        plan = plan.with_user(self.manager)
        plan.action_plan()
        plan.action_start()
        plan.release_note = "Released after sea trial."
        plan.action_complete()

    def test_dry_dock_restarts_checkpoint_count_from_current_hours(self):
        equipment = self._new_metered_equipment()
        task = self._task(equipment, 300)
        self._reading(equipment, 290, fields.Datetime.now() - timedelta(days=2))
        self._complete(task)
        self._reading(equipment, 1000, fields.Datetime.now() - timedelta(days=1))
        self.assertEqual((task.cycle, task.next_checkpoint_hours, task.state), (1, 600, "overdue"))

        self._finish_dry_dock(self._dry_dock())
        self.assertEqual((task.cycle, task.cycle_start_hours), (2, 1000))
        self.assertEqual((task.next_checkpoint_hours, task.state), (1300, "not_due"))
        self.assertEqual(len(task.completion_ids), 1)
        self._reading(equipment, 1290, fields.Datetime.now() - timedelta(hours=1))
        self._complete(task)
        self.assertEqual(task.next_checkpoint_hours, 1600)
        with self.assertRaises(AccessError):
            task.with_user(self.maintenance_user).write({"cycle": 9})

    def test_dry_dock_can_leave_checkpoint_counts_alone(self):
        equipment = self._new_metered_equipment()
        task = self._task(equipment, 300)
        self._reading(equipment, 100, fields.Datetime.now() - timedelta(days=1))
        self._finish_dry_dock(self._dry_dock(reset_pm_counters=False))
        self.assertEqual((task.cycle, task.next_checkpoint_hours), (1, 300))

    def test_report_records_the_paper_form_columns(self):
        engine = self._new_metered_equipment(name="Paper Form Engine")
        self._reading(engine, 100, fields.Datetime.now() - timedelta(days=1))
        Report = self.env["sedar.daily.engine.report"].with_user(self.maintenance_user)
        report = Report.create({
            "tugboat_id": self.tug.id,
            "rob_diesel": 5800, "rob_lube_40": 330, "rob_lube_15w40": 160, "rob_hydraulic": 55, "rob_fresh_water": 6,
            "line_ids": [(0, 0, {
                "equipment_id": engine.id, "time_start": 11 + 20 / 60, "time_stop": 13 + 40 / 60,
                "hours_run": 2 + 20 / 60, "fuel_consumed": 150, "fuel_rob": 1300,
                "rpm": 1800, "oil_pressure": 4.5, "water_temp": 70, "lube_oil_refill": 2,
            })],
        })
        line = report.line_ids
        line.time_start, line.time_stop = 22.0, 2.0
        line._onchange_times()
        self.assertEqual(line.hours_run, 4.0)
        with self.assertRaises(ValidationError):
            line.time_stop = 24
        with self.assertRaises(ValidationError):
            line.rpm = -1
        with self.assertRaises(ValidationError):
            report.rob_diesel = -1
        report.action_post()
        self.assertEqual(report.posted_by_id, self.maintenance_user)
        self.assertEqual(engine.sedar_current_running_hours, 104)

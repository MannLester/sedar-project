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

    def _new_metered_equipment(self, name="Metered Test Engine", technician=None, interval=100):
        return self.env["maintenance.equipment"].create({
            "name": name,
            "category_id": self.category.id,
            "maintenance_team_id": self.team.id,
            "technician_user_id": technician.id if technician else False,
            "sedar_tugboat_id": self.tug.id,
            "sedar_system": "propulsion",
            "sedar_criticality": "critical",
            "sedar_running_interval_hours": interval,
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

    def _completed_planned_order(self, equipment, service_reading):
        return self.env["maintenance.request"].create({
            "name": f"Completed service for {equipment.name}",
            "maintenance_type": "preventive",
            "equipment_id": equipment.id,
            "sedar_work_order_type": "planned",
            "sedar_availability_impact": "none",
            "stage_id": self.done_stage.id,
            "close_date": fields.Datetime.now(),
            "sedar_service_reading_id": service_reading.id,
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

    def test_open_drydock_plan_keeps_tug_on_maintenance_hold_until_completed(self):
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
        self.assertEqual(self.tug.availability_status, "maintenance")

        work_order.sedar_closure_note = "Corrective work verified."
        work_order.with_user(self.manager).action_sedar_release_tug()
        self.assertEqual(self.tug.availability_status, "maintenance")

        with self.assertRaises(UserError):
            plan.with_user(self.manager).action_complete()

        plan.release_note = "Dry dock sea trial completed."
        plan.with_user(self.manager).action_start()
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

    def test_verified_service_baseline_creates_one_activity_and_never_procurement(self):
        equipment = self._new_metered_equipment(
            name="Due Alert Test Engine", technician=self.maintenance_user, interval=100
        )
        now = fields.Datetime.now()
        baseline = self._reading(equipment, 100, now - timedelta(days=3))
        work_order = self._completed_planned_order(equipment, baseline)

        with self.assertRaises(AccessError):
            work_order.with_user(self.maintenance_user).action_sedar_verify_service_baseline()

        work_order.with_user(self.manager).action_sedar_verify_service_baseline()
        verified_at = work_order.sedar_service_baseline_verified_at
        work_order.with_user(self.manager).action_sedar_verify_service_baseline()
        self.assertEqual(work_order.sedar_service_baseline_verified_at, verified_at)
        self.assertEqual(equipment.sedar_service_due_state, "not_due")
        self.assertEqual(equipment.sedar_verified_service_work_order_id, work_order)
        self.assertEqual(equipment.sedar_last_service_hours, 100)
        with self.assertRaises(AccessError):
            equipment.with_user(self.maintenance_user).with_context(
                sedar_allow_service_audit_write=True
            ).write({"sedar_last_service_hours": 999})
        with self.assertRaises(AccessError):
            work_order.with_user(self.manager).with_context(
                sedar_allow_service_audit_write=True
            ).write({"sedar_running_hours_at_service": 999})
        with self.assertRaises(AccessError):
            self.env["maintenance.equipment"].with_user(self.maintenance_user).create({
                "name": "Forged Service Baseline Equipment",
                "sedar_last_service_hours": 999,
            })
        with self.assertRaises(AccessError):
            self.env["maintenance.request"].with_user(self.manager).create({
                "name": "Forged Service Baseline Work Order",
                "sedar_service_baseline_verified_at": fields.Datetime.now(),
            })

        purchase_count = None
        if "sedar.purchase.request" in self.env.registry:
            purchase_count = self.env["sedar.purchase.request"].search_count([])
        availability_before = self.tug.availability_status

        self._reading(equipment, 200, now - timedelta(hours=1))
        equipment._sedar_reconcile_due_activity()
        equipment._sedar_reconcile_due_activity()
        activities = equipment._sedar_open_due_activities()

        self.assertEqual(equipment.sedar_service_due_state, "due")
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.maintenance_user)
        self.assertEqual(
            equipment.sedar_alerted_service_cycle_key,
            equipment.sedar_service_cycle_key,
        )

        activities.action_feedback(feedback="Acknowledged for planning.")
        equipment._sedar_reconcile_due_activity()
        self.assertFalse(equipment._sedar_open_due_activities())
        self._reading(equipment, 205, now - timedelta(minutes=30))
        self.assertEqual(equipment.sedar_service_due_state, "overdue")
        self.assertFalse(equipment._sedar_open_due_activities())
        self.assertEqual(self.tug.availability_status, availability_before)
        if purchase_count is not None:
            self.assertEqual(
                self.env["sedar.purchase.request"].search_count([]), purchase_count
            )

    def test_manager_correction_closes_stale_alert_and_preserves_service_baseline(self):
        equipment = self._new_metered_equipment(
            name="Corrected Due Test Engine", technician=self.manager, interval=100
        )
        now = fields.Datetime.now()
        baseline = self._reading(equipment, 100, now - timedelta(days=3))
        work_order = self._completed_planned_order(equipment, baseline)
        work_order.with_user(self.manager).action_sedar_verify_service_baseline()
        due_reading = self._reading(equipment, 200, now - timedelta(hours=2))
        self.assertEqual(len(equipment._sedar_open_due_activities()), 1)

        correction = self._reading(
            equipment,
            190,
            due_reading.reading_at,
            user=self.manager,
            supersedes_reading_id=due_reading.id,
            correction_reason="The photographed meter shows 190.00 hours.",
        )
        self.assertEqual(equipment.sedar_current_running_hour_reading_id, correction)
        self.assertEqual(equipment.sedar_service_due_state, "not_due")
        self.assertFalse(equipment._sedar_open_due_activities())
        self.assertFalse(equipment.sedar_alerted_service_cycle_key)
        self.assertEqual(equipment.sedar_verified_service_reading_id, baseline)

        self._reading(equipment, 200, now - timedelta(minutes=15))
        self.assertEqual(equipment.sedar_service_due_state, "due")
        self.assertEqual(len(equipment._sedar_open_due_activities()), 1)

    def test_company_fallback_receives_due_alert_without_equipment_technician(self):
        self.env.company.sedar_maintenance_fallback_user_id = self.manager
        equipment = self._new_metered_equipment(
            name="Fallback Alert Test Engine", technician=None, interval=50
        )
        now = fields.Datetime.now()
        baseline = self._reading(equipment, 100, now - timedelta(days=2))
        work_order = self._completed_planned_order(equipment, baseline)
        work_order.with_user(self.manager).action_sedar_verify_service_baseline()
        self._reading(equipment, 150, now - timedelta(hours=1))

        self.assertEqual(equipment.sedar_due_alert_assignment_state, "assigned")
        self.assertEqual(equipment._sedar_open_due_activities().user_id, self.manager)

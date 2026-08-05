from datetime import datetime

from odoo.exceptions import UserError, ValidationError
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

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAutomatedMarineLifecycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"].create({"name": "Lifecycle Test Client"})
        port = cls.env["sedar.marine.port"].create({"name": "Test Port", "code": "LIFE"})
        tug_class = cls.env["sedar.tug.class"].create({"name": "Lifecycle Tug"})
        service = cls.env["sedar.marine.service.type"].create({
            "name": "Lifecycle Assist", "code": "LIFECYCLE", "pricing_basis": "per_service",
        })
        tug = cls.env["sedar.tugboat"].create({
            "name": "Lifecycle Tug", "registration_number": "LIFE-001",
            "tug_class_id": tug_class.id, "availability_status": "available",
        })
        rank = cls.env["sedar.crew.rank"].create({"name": "Tug Master", "code": "MASTER-LIFE"})
        employee = cls.env["hr.employee"].create({"name": "Lifecycle Master"})
        profile = cls.env["sedar.crew.profile"].create({
            "employee_id": employee.id, "employee_number": "LIFE-MASTER",
            "rank_id": rank.id, "availability_status": "available",
        })
        start = fields.Datetime.now()
        cls.order = cls.env["sedar.marine.service.order"].create({
            "client_id": partner.id, "assisted_vessel_name": "MV Lifecycle",
            "service_type_id": service.id, "number_of_tugs": 1,
            "scope_of_work": "Lifecycle test", "port_id": port.id,
            "requested_start": start, "estimated_duration_hours": 2,
            "state": "planning",
        })
        cls.assignment = cls.env["sedar.tug.assignment"].create({
            "order_id": cls.order.id, "tugboat_id": tug.id,
        })
        requirement = cls.env["sedar.manning.requirement"].create({
            "tug_assignment_id": cls.assignment.id, "rank_id": rank.id, "required_count": 1,
        })
        cls.crew_assignment = cls.env["sedar.crew.assignment"].create({
            "requirement_id": requirement.id, "crew_profile_id": profile.id,
        })

    def test_inventory_gate_creates_one_awaiting_operation(self):
        self.assertEqual(self.order.readiness_status, "waiting_inventory")
        self.order.action_confirm_inventory_ready()
        self.assertEqual(self.order.state, "ready")
        self.assertEqual(len(self.order.operation_ids), 1)
        self.assertEqual(self.order.operation_ids.state, "awaiting_start")
        self.order._sync_automated_readiness()
        self.assertEqual(len(self.order.operation_ids), 1)

    def test_tug_times_drive_start_completion_and_reopen(self):
        self.order.action_confirm_inventory_ready()
        start = fields.Datetime.now()
        self.assignment.with_context(sedar_completion_action=True).write({"actual_start": start})
        self.assertEqual(self.order.state, "in_progress")
        self.assertEqual(self.order.operation_ids.state, "in_progress")
        self.assignment.with_context(sedar_completion_action=True).write({
            "actual_end": start + timedelta(hours=2),
            "completion_note": "Lifecycle complete",
            "completion_state": "submitted",
        })
        self.assertEqual(self.order.state, "completed")
        self.assertEqual(self.order.operation_ids.state, "completed")
        self.assignment.with_context(sedar_completion_action=True).write({"completion_state": "returned"})
        self.assertEqual(self.order.state, "in_progress")
        self.assertEqual(self.order.operation_ids.state, "in_progress")

    def test_relevant_change_resets_inventory_confirmation(self):
        self.order.action_confirm_inventory_ready()
        self.order.write({"scope_of_work": "Changed lifecycle scope"})
        self.assertFalse(self.order.inventory_ready)
        self.assertFalse(self.order.inventory_ready_by_id)
        self.assertFalse(self.order.inventory_ready_at)
        self.assertEqual(self.order.state, "blocked")

    def test_dispatch_snapshot_inherits_service_order_company(self):
        self.order.action_confirm_inventory_ready()
        operation = self.order.operation_ids
        self.assertEqual(operation.company_id, self.order.company_id)
        self.assertEqual(operation.tug_operation_ids.company_id, self.order.company_id)
        self.assertEqual(operation.tug_operation_ids.crew_manifest_ids.company_id, self.order.company_id)

    def test_operation_tug_rejects_assignment_from_another_order(self):
        other_order = self.order.copy({
            "assisted_vessel_name": "MV Other Lifecycle",
            "state": "planning",
        })
        other_assignment = self.assignment.copy({"order_id": other_order.id})
        operation = self.env["sedar.marine.operation"].create({"order_id": self.order.id})
        with self.assertRaisesRegex(ValidationError, "must belong"):
            self.env["sedar.marine.operation.tug"].create({
                "operation_id": operation.id,
                "tug_assignment_id": other_assignment.id,
                "tugboat_id": other_assignment.tugboat_id.id,
            })

    def test_assignment_cannot_move_after_operation_snapshot(self):
        operation = self.env["sedar.marine.operation"].create({"order_id": self.order.id})
        self.env["sedar.marine.operation.tug"].create({
            "operation_id": operation.id,
            "tug_assignment_id": self.assignment.id,
            "tugboat_id": self.assignment.tugboat_id.id,
        })
        other_order = self.order.copy({
            "assisted_vessel_name": "MV Assignment Reparenting Is Forbidden",
            "state": "planning",
        })

        with self.assertRaisesRegex(ValidationError, "cannot move"):
            self.assignment.write({"order_id": other_order.id})

        self.assertEqual(self.assignment.order_id, self.order)

    def test_snapshot_sources_cannot_be_reparented(self):
        operation = self.env["sedar.marine.operation"].create({"order_id": self.order.id})
        operation_tug = self.env["sedar.marine.operation.tug"].create({
            "operation_id": operation.id,
            "tug_assignment_id": self.assignment.id,
            "tugboat_id": self.assignment.tugboat_id.id,
        })
        self.env["sedar.marine.operation.crew"].create({
            "operation_tug_id": operation_tug.id,
            "crew_assignment_id": self.crew_assignment.id,
            "crew_profile_id": self.crew_assignment.crew_profile_id.id,
            "employee_name": self.crew_assignment.employee_id.name,
        })
        other_order = self.order.copy({
            "assisted_vessel_name": "MV Snapshot Source Reparenting Is Forbidden",
            "state": "planning",
        })
        other_assignment = self.assignment.copy({"order_id": other_order.id})
        other_requirement = self.crew_assignment.requirement_id.copy({
            "tug_assignment_id": other_assignment.id,
        })

        with self.assertRaisesRegex(ValidationError, "crew assignment cannot move"):
            self.crew_assignment.write({"requirement_id": other_requirement.id})
        with self.assertRaisesRegex(ValidationError, "manning requirement cannot move"):
            self.crew_assignment.requirement_id.write({
                "tug_assignment_id": other_assignment.id,
            })
        with self.assertRaisesRegex(ValidationError, "snapshot cannot move"):
            operation_tug.write({"tug_assignment_id": other_assignment.id})
        other_operation = self.env["sedar.marine.operation"].create({
            "order_id": other_order.id,
        })
        with self.assertRaisesRegex(ValidationError, "snapshot cannot move"):
            operation_tug.write({"operation_id": other_operation.id})

    def test_operation_cannot_move_to_another_service_order(self):
        self.order.action_confirm_inventory_ready()
        operation = self.order.operation_ids
        other_order = self.order.copy({
            "assisted_vessel_name": "MV Reparenting Is Forbidden",
            "state": "planning",
        })

        with self.assertRaisesRegex(ValidationError, "cannot move"):
            operation.write({"order_id": other_order.id})

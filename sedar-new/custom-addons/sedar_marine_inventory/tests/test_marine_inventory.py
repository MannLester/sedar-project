from datetime import datetime

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMarineInventory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.product"].create({
            "name": "Inventory Test Diesel",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.unit.id,
        })
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.stock_location, 100)
        cls.partner = cls.env["res.partner"].create({"name": "Inventory Client"})
        cls.port = cls.env["sedar.marine.port"].create({"name": "Inventory Port", "code": "INV"})
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Inventory Assist",
            "code": "INV-A",
            "pricing_basis": "per_service",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Inventory Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Inventory Test Tug",
            "registration_number": "INV-TUG",
            "tug_class_id": cls.tug_class.id,
            "availability_status": "available",
        })
        cls.other_tug = cls.env["sedar.tugboat"].create({
            "name": "Incompatible Inventory Tug",
            "registration_number": "INV-TUG-OTHER",
            "tug_class_id": cls.tug_class.id,
            "availability_status": "available",
        })
        cls.inventory_manager = cls.env["res.users"].create({
            "name": "Inventory Test Manager",
            "login": "inventory.manager@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_marine_inventory.group_marine_inventory_manager").id,
            ])],
        })
        cls.template = cls.env["sedar.inventory.template"].create({
            "name": "Inventory Test Template",
            "service_type_id": cls.service.id,
            "source_location_id": cls.stock_location.id,
            "line_ids": [(0, 0, {"product_id": cls.product.id, "required_qty": 50, "per_tug": True})],
        })

    def _make_order(self):
        return self.env["sedar.marine.service.order"].create({
            "client_id": self.partner.id,
            "assisted_vessel_name": "MV Inventory Test",
            "service_type_id": self.service.id,
            "number_of_tugs": 1,
            "scope_of_work": "Inventory readiness test.",
            "port_id": self.port.id,
            "requested_start": datetime(2026, 9, 6, 8, 0, 0),
            "estimated_duration_hours": 2,
            "state": "planning",
        })

    def test_service_order_inventory_requirement_drives_readiness_component(self):
        order = self._make_order()
        order.action_generate_inventory_requirements()
        self.assertTrue(order.inventory_requirement_ids)
        self.assertTrue(order.inventory_auto_ready)
        self.assertTrue(order.inventory_ready)

        line = order.inventory_requirement_ids[:1]
        line.required_qty = 200
        self.assertEqual(line.readiness_state, "shortage")
        self.assertFalse(order.inventory_auto_ready)
        self.assertFalse(order.inventory_ready)
        with self.assertRaises(UserError):
            order.action_confirm_inventory_ready()

    def test_maintenance_part_issue_consumes_stock_quantity(self):
        work_order = self.env["maintenance.request"].create({
            "name": "Inventory Part Test",
            "maintenance_type": "corrective",
            "sedar_tugboat_id": self.tug.id,
            "sedar_work_order_type": "defect",
            "sedar_defect_source": "Inventory test",
        })
        line = self.env["sedar.maintenance.part.line"].create({
            "maintenance_request_id": work_order.id,
            "product_id": self.product.id,
            "source_location_id": self.stock_location.id,
            "requested_qty": 5,
        })
        before = line._sedar_available_qty(self.product, self.stock_location)
        line.action_reserve()
        line.action_issue()
        line.action_consume()
        after = line._sedar_available_qty(self.product, self.stock_location)
        self.assertEqual(before - after, 5)
        self.assertEqual(line.state, "consumed")

    def test_inventory_check_uses_exact_warehouse_balance_and_reorder_status(self):
        child_location = self.env["stock.location"].create({
            "name": "Inventory Test Child",
            "usage": "internal",
            "location_id": self.stock_location.id,
            "company_id": self.company.id,
        })
        self.env["stock.quant"]._update_available_quantity(self.product, child_location, 50)
        self.product.write({
            "default_code": "SEDAR-TEST-001",
            "sedar_inventory_item": True,
            "sedar_manufacturer_part_number": "MPN-TEST-001",
            "sedar_reorder_point": 120,
        })

        self.assertEqual(self.product.sedar_on_hand_qty, 100)
        self.assertEqual(self.product.sedar_available_to_issue, 100)
        self.assertEqual(self.product.sedar_stock_status, "low_stock")

    def test_issue_to_tug_deducts_stock_and_creates_immutable_audit_record(self):
        self.product.write({
            "default_code": "SEDAR-TEST-002",
            "sedar_inventory_item": True,
            "sedar_manufacturer_part_number": "MPN-TEST-002",
            "sedar_compatibility_scope": "restricted",
            "sedar_compatible_tugboat_ids": [Command.set(self.tug.ids)],
            "sedar_reorder_point": 10,
        })
        before = self.product.sedar_available_to_issue
        issue = self.env["sedar.inventory.issue"].with_user(self.inventory_manager)._issue_to_tug(
            self.product,
            self.tug,
            5,
            "Inventory test issue.",
            self.stock_location,
        )

        self.assertEqual(before - self.product.sedar_available_to_issue, 5)
        self.assertEqual(issue.tugboat_id, self.tug)
        self.assertEqual(issue.issued_by_id, self.inventory_manager)
        self.assertEqual(issue.stock_move_id.state, "done")
        self.assertEqual(issue.stock_move_id.location_dest_id.usage, "inventory")
        with self.assertRaises(AccessError):
            issue.with_user(self.inventory_manager).write({"purpose": "Changed"})
        with self.assertRaises(AccessError):
            issue.with_user(self.inventory_manager).unlink()
        with self.assertRaises(UserError):
            self.product.write({"default_code": "SEDAR-TEST-CHANGED"})

    def test_issue_to_tug_hard_blocks_incompatibility_and_insufficient_stock(self):
        self.product.write({
            "default_code": "SEDAR-TEST-003",
            "sedar_inventory_item": True,
            "sedar_compatibility_scope": "restricted",
            "sedar_compatible_tugboat_ids": [Command.set(self.tug.ids)],
        })
        Issue = self.env["sedar.inventory.issue"].with_user(self.inventory_manager)
        with self.assertRaises(UserError):
            Issue._issue_to_tug(
                self.product, self.other_tug, 1, "Wrong tug.", self.stock_location
            )
        with self.assertRaises(UserError):
            Issue._issue_to_tug(
                self.product, self.tug, 101, "Too many.", self.stock_location
            )

    def test_demo_consumed_fuel_log_has_completed_stock_moves(self):
        fuel_log = self.env.ref("sedar_marine_inventory.fuel_completed_operation")

        self.assertEqual(fuel_log.state, "consumed")
        self.assertEqual(len(fuel_log.stock_move_ids), 2)
        self.assertEqual(set(fuel_log.stock_move_ids.mapped("state")), {"done"})
        consumption_move = fuel_log.stock_move_ids.filtered(
            lambda move: move.location_dest_id.usage == "inventory"
        )
        self.assertEqual(len(consumption_move), 1)
        self.assertEqual(consumption_move.quantity, fuel_log.consumed_qty)

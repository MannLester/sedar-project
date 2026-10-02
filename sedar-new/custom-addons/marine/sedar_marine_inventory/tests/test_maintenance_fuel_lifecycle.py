from datetime import datetime

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaintenanceFuelLifecycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.storage = cls.warehouse.lot_stock_id
        cls.storage.write({"sedar_location_role": "storage"})
        virtual = cls.env["stock.location"].search(
            [("usage", "=", "view"), ("company_id", "in", [False, cls.company.id])],
            order="company_id desc, id",
            limit=1,
        )
        cls.consumption = cls.env["stock.location"].create(
            {
                "name": "Maintenance and Fuel Consumption",
                "usage": "inventory",
                "location_id": virtual.id,
                "company_id": cls.company.id,
                "sedar_location_role": "consumption",
            }
        )
        cls.tug_class = cls.env["sedar.tug.class"].create(
            {"name": "Maintenance Fuel Tug Class"}
        )
        cls.tug = cls.env["sedar.tugboat"].create(
            {
                "name": "Maintenance Fuel Tug",
                "registration_number": "MAINT-FUEL-TUG",
                "tug_class_id": cls.tug_class.id,
                "company_id": cls.company.id,
            }
        )
        cls.tug_location = cls.env["stock.location"].create(
            {
                "name": "Maintenance Fuel Tug Stock",
                "usage": "internal",
                "location_id": cls.storage.location_id.id,
                "company_id": cls.company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": cls.tug.id,
            }
        )
        cls.tug.stock_location_id = cls.tug_location
        inventory_group = cls.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        user_groups = [
            cls.env.ref("base.group_user").id,
            inventory_group.id,
        ]
        cls.officer = cls.env["res.users"].create(
            {
                "name": "Maintenance Fuel Exact Officer",
                "login": "maintenance.fuel.officer@test.example",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [Command.set(user_groups)],
            }
        )
        cls.other_manager = cls.env["res.users"].create(
            {
                "name": "Maintenance Fuel Other Manager",
                "login": "maintenance.fuel.other@test.example",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [Command.set(user_groups)],
            }
        )
        cls.company.write(
            {
                "sedar_procurement_inventory_officer_id": cls.officer.id,
                "sedar_default_storage_location_id": cls.storage.id,
                "sedar_consumption_location_id": cls.consumption.id,
            }
        )
        cls.spare = cls.env["product.product"].create(
            {
                "name": "Lifecycle Maintenance Spare",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.unit.id,
                "default_code": "LIFECYCLE-MAINT-SPARE",
                "sedar_inventory_item": True,
                "sedar_item_type": "spare_consumable",
            }
        )
        cls.fuel = cls.env["product.product"].create(
            {
                "name": "Lifecycle Operation Fuel",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.unit.id,
                "default_code": "LIFECYCLE-OP-FUEL",
                "sedar_inventory_item": True,
                "sedar_item_type": "fuel_lubricant",
            }
        )
        cls.env["stock.quant"]._update_available_quantity(cls.spare, cls.storage, 50)
        cls.env["stock.quant"]._update_available_quantity(cls.fuel, cls.storage, 100)
        cls.work_order = cls.env["maintenance.request"].create(
            {
                "name": "Lifecycle Maintenance Work Order",
                "company_id": cls.company.id,
                "maintenance_type": "corrective",
                "sedar_tugboat_id": cls.tug.id,
                "sedar_work_order_type": "defect",
                "sedar_defect_source": "Lifecycle integration test",
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Maintenance Fuel Client"})
        cls.port = cls.env["sedar.marine.port"].create(
            {"name": "Maintenance Fuel Port", "code": "MFP"}
        )
        cls.service = cls.env["sedar.marine.service.type"].create(
            {
                "name": "Maintenance Fuel Service",
                "code": "MF-SVC",
                "pricing_basis": "per_service",
            }
        )
        order = cls.env["sedar.marine.service.order"].create(
            {
                "company_id": cls.company.id,
                "client_id": cls.partner.id,
                "assisted_vessel_name": "MV Lifecycle Fuel",
                "service_type_id": cls.service.id,
                "number_of_tugs": 1,
                "scope_of_work": "Fuel lifecycle integration test.",
                "port_id": cls.port.id,
                "requested_start": datetime(2026, 9, 10, 8, 0),
                "estimated_duration_hours": 2,
                "state": "planning",
            }
        )
        cls.operation = cls.env["sedar.marine.operation"].create({"order_id": order.id})

    def _part_line(self):
        return self.env["sedar.maintenance.part.line"].create(
            {
                "maintenance_request_id": self.work_order.id,
                "product_id": self.spare.id,
                "source_location_id": self.storage.id,
                "requested_qty": 5,
            }
        )

    def _fuel_log(self, issue_qty=10):
        return self.env["sedar.operation.fuel.log"].create(
            {
                "operation_id": self.operation.id,
                "tugboat_id": self.tug.id,
                "product_id": self.fuel.id,
                "source_location_id": self.storage.id,
                "tug_location_id": self.tug_location.id,
                "quantity_to_issue": issue_qty,
            }
        )

    def test_maintenance_issue_and_consumption_use_one_lifecycle(self):
        line = self._part_line().with_user(self.officer)

        line.action_reserve()
        line.action_issue()

        self.assertEqual(line.issued_qty, 5)
        self.assertEqual(len(line.lifecycle_ids), 1)
        self.assertEqual(line.lifecycle_ids.open_qty, 5)
        self.assertEqual(
            line.lifecycle_ids.issue_move_id.location_dest_id, self.tug_location
        )
        with self.assertRaises(UserError):
            line.action_issue()

        line.action_consume()

        self.assertEqual(line.consumed_qty, 5)
        self.assertEqual(line.state, "consumed")
        self.assertEqual(line.lifecycle_ids.state, "closed")
        self.assertEqual(len(line.stock_move_ids), 2)
        with self.assertRaises(UserError):
            line.action_consume()

    def test_exact_officer_controls_maintenance_stock_disposition(self):
        line = self._part_line()

        with self.assertRaises(AccessError):
            line.with_user(self.other_manager).action_reserve()
        with self.assertRaises(AccessError):
            line.with_user(self.other_manager).action_issue()

    def test_maintenance_part_rejects_cross_company_storage(self):
        other_company = self.env["res.company"].create(
            {"name": "Other Maintenance Inventory Company"}
        )
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Other Maintenance Warehouse",
                "code": "OMWH",
                "company_id": other_company.id,
            }
        )

        with self.assertRaises(ValidationError):
            self.env["sedar.maintenance.part.line"].create(
                {
                    "maintenance_request_id": self.work_order.id,
                    "product_id": self.spare.id,
                    "source_location_id": other_warehouse.lot_stock_id.id,
                    "requested_qty": 1,
                }
            )

    def test_fuel_issue_and_partial_consumption_derive_from_lifecycle(self):
        log = self._fuel_log().with_user(self.officer)

        log.action_issue_to_tug()
        log.quantity_to_consume = 4
        log.action_record_consumption()

        self.assertEqual(log.issued_qty, 10)
        self.assertEqual(log.consumed_qty, 4)
        self.assertEqual(log.remaining_qty, 6)
        self.assertEqual(log.lifecycle_ids.open_qty, 6)
        self.assertEqual(len(log.stock_move_ids), 2)
        with self.assertRaises(UserError):
            log.action_record_consumption()

    def test_fuel_duplicate_and_over_consumption_are_rejected(self):
        log = self._fuel_log(issue_qty=3).with_user(self.officer)
        log.action_issue_to_tug()
        log.quantity_to_consume = 3
        log.action_record_consumption()

        log.quantity_to_consume = 1
        with self.assertRaises(UserError):
            log.action_record_consumption()
        self.assertEqual(len(log.lifecycle_ids.event_ids), 1)

    def test_exact_officer_controls_fuel_and_company_links(self):
        log = self._fuel_log()

        with self.assertRaises(AccessError):
            log.with_user(self.other_manager).action_issue_to_tug()

        other_company = self.env["res.company"].create({"name": "Other Fuel Company"})
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Other Fuel Warehouse",
                "code": "OFW2",
                "company_id": other_company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["sedar.operation.fuel.log"].create(
                {
                    "operation_id": self.operation.id,
                    "tugboat_id": self.tug.id,
                    "product_id": self.fuel.id,
                    "source_location_id": other_warehouse.lot_stock_id.id,
                    "tug_location_id": self.tug_location.id,
                }
            )

    def test_init_preserves_legacy_counters_once(self):
        line = self._part_line()
        log = self._fuel_log()
        migration_cases = (
            ("sedar_maintenance_part_line", line),
            ("sedar_operation_fuel_log", log),
        )

        for table, record in migration_cases:
            self.env.cr.execute(
                f"""
                UPDATE {table}
                   SET issued_qty = 7,
                       consumed_qty = 3,
                       legacy_issued_qty = NULL,
                       legacy_consumed_qty = NULL
                 WHERE id = %s
                """,
                [record.id],
            )
            record.init()
            record.invalidate_recordset(["legacy_issued_qty", "legacy_consumed_qty"])
            self.assertEqual(record.legacy_issued_qty, 7)
            self.assertEqual(record.legacy_consumed_qty, 3)

            self.env.cr.execute(
                f"""
                UPDATE {table}
                   SET issued_qty = 9,
                       consumed_qty = 5
                 WHERE id = %s
                """,
                [record.id],
            )
            record.init()
            record.invalidate_recordset(["legacy_issued_qty", "legacy_consumed_qty"])
            self.assertEqual(record.legacy_issued_qty, 7)
            self.assertEqual(record.legacy_consumed_qty, 3)

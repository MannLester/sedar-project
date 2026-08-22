import importlib.util
from datetime import datetime
from pathlib import Path

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMarineInventory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Inventory Test Diesel",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.unit.id,
            }
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.stock_location, 100
        )
        cls.partner = cls.env["res.partner"].create({"name": "Inventory Client"})
        cls.port = cls.env["sedar.marine.port"].create(
            {"name": "Inventory Port", "code": "INV"}
        )
        cls.service = cls.env["sedar.marine.service.type"].create(
            {
                "name": "Inventory Assist",
                "code": "INV-A",
                "pricing_basis": "per_service",
            }
        )
        cls.tug_class = cls.env["sedar.tug.class"].create(
            {"name": "Inventory Tug Class"}
        )
        cls.tug = cls.env["sedar.tugboat"].create(
            {
                "name": "Inventory Test Tug",
                "registration_number": "INV-TUG",
                "tug_class_id": cls.tug_class.id,
                "availability_status": "available",
            }
        )
        cls.other_tug = cls.env["sedar.tugboat"].create(
            {
                "name": "Incompatible Inventory Tug",
                "registration_number": "INV-TUG-OTHER",
                "tug_class_id": cls.tug_class.id,
                "availability_status": "available",
            }
        )
        cls.tug_location = cls.env["stock.location"].create(
            {
                "name": "Inventory Test Tug Stock",
                "usage": "internal",
                "location_id": cls.stock_location.location_id.id,
                "company_id": cls.company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": cls.tug.id,
            }
        )
        cls.tug.stock_location_id = cls.tug_location
        cls.inventory_manager = cls.env["res.users"].create(
            {
                "name": "Inventory Test Manager",
                "login": "inventory.manager@test.example",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(
                                "sedar_marine_inventory.group_marine_inventory_manager"
                            ).id,
                        ]
                    )
                ],
            }
        )
        cls.company.sedar_procurement_inventory_officer_id = cls.inventory_manager
        cls.template = cls.env["sedar.inventory.template"].create(
            {
                "name": "Inventory Test Template",
                "service_type_id": cls.service.id,
                "source_location_id": cls.stock_location.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "required_qty": 50,
                            "per_tug": True,
                        },
                    )
                ],
            }
        )

    def _make_order(self):
        return self.env["sedar.marine.service.order"].create(
            {
                "client_id": self.partner.id,
                "assisted_vessel_name": "MV Inventory Test",
                "service_type_id": self.service.id,
                "number_of_tugs": 1,
                "scope_of_work": "Inventory readiness test.",
                "port_id": self.port.id,
                "requested_start": datetime(2026, 9, 6, 8, 0, 0),
                "estimated_duration_hours": 2,
                "state": "planning",
            }
        )

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
        spare = self.env["product.product"].create(
            {
                "name": "Inventory Lifecycle Spare",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.unit.id,
                "default_code": "INVENTORY-LIFECYCLE-SPARE",
                "sedar_inventory_item": True,
                "sedar_item_type": "spare_consumable",
            }
        )
        self.env["stock.quant"]._update_available_quantity(
            spare, self.stock_location, 10
        )
        work_order = self.env["maintenance.request"].create(
            {
                "name": "Inventory Part Test",
                "maintenance_type": "corrective",
                "sedar_tugboat_id": self.tug.id,
                "sedar_work_order_type": "defect",
                "sedar_defect_source": "Inventory test",
            }
        )
        line = self.env["sedar.maintenance.part.line"].create(
            {
                "maintenance_request_id": work_order.id,
                "product_id": spare.id,
                "source_location_id": self.stock_location.id,
                "requested_qty": 5,
            }
        )
        before = line._sedar_available_qty(spare, self.stock_location)
        line = line.with_user(self.inventory_manager)
        line.action_reserve()
        line.action_issue()
        line.action_consume()
        after = line._sedar_available_qty(spare, self.stock_location)
        self.assertEqual(before - after, 5)
        self.assertEqual(line.state, "consumed")

    def test_inventory_check_uses_exact_warehouse_balance_and_reorder_status(self):
        child_location = self.env["stock.location"].create(
            {
                "name": "Inventory Test Child",
                "usage": "internal",
                "location_id": self.stock_location.id,
                "company_id": self.company.id,
            }
        )
        self.env["stock.quant"]._update_available_quantity(
            self.product, child_location, 50
        )
        self.product.write(
            {
                "default_code": "SEDAR-TEST-001",
                "sedar_inventory_item": True,
                "sedar_manufacturer_part_number": "MPN-TEST-001",
                "sedar_reorder_point": 120,
            }
        )

        self.assertEqual(self.product.sedar_on_hand_qty, 100)
        self.assertEqual(self.product.sedar_available_to_issue, 100)
        self.assertEqual(self.product.sedar_stock_status, "low_stock")

    def test_issue_to_tug_deducts_stock_and_creates_immutable_audit_record(self):
        self.product.write(
            {
                "default_code": "SEDAR-TEST-002",
                "sedar_inventory_item": True,
                "sedar_manufacturer_part_number": "MPN-TEST-002",
                "sedar_compatibility_scope": "restricted",
                "sedar_compatible_tugboat_ids": [Command.set(self.tug.ids)],
                "sedar_reorder_point": 10,
            }
        )
        before = self.product.sedar_available_to_issue
        issue = (
            self.env["sedar.inventory.issue"]
            .with_user(self.inventory_manager)
            ._issue_to_tug(
                self.product,
                self.tug,
                5,
                "Inventory test issue.",
                self.stock_location,
            )
        )

        self.assertEqual(before - self.product.sedar_available_to_issue, 5)
        self.assertEqual(issue.tugboat_id, self.tug)
        self.assertEqual(issue.issued_by_id, self.inventory_manager)
        self.assertEqual(issue.stock_move_id.state, "done")
        self.assertEqual(
            issue.stock_move_id.location_dest_id, self.tug.stock_location_id
        )
        self.assertEqual(issue.lifecycle_id.open_qty, 5)
        with self.assertRaises(AccessError):
            issue.with_user(self.inventory_manager).write({"purpose": "Changed"})
        with self.assertRaises(AccessError):
            issue.with_user(self.inventory_manager).unlink()
        with self.assertRaises(UserError):
            self.product.write({"default_code": "SEDAR-TEST-CHANGED"})

    def test_issue_to_tug_hard_blocks_incompatibility_and_insufficient_stock(self):
        self.product.write(
            {
                "default_code": "SEDAR-TEST-003",
                "sedar_inventory_item": True,
                "sedar_compatibility_scope": "restricted",
                "sedar_compatible_tugboat_ids": [Command.set(self.tug.ids)],
            }
        )
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
        self.assertFalse(fuel_log.lifecycle_ids)
        self.assertFalse(fuel_log.stock_move_ids)
        self.assertEqual(fuel_log.legacy_issued_qty, 850)
        self.assertEqual(fuel_log.legacy_consumed_qty, 620)

    def test_requirements_and_templates_follow_service_order_company(self):
        other_company = self.env["res.company"].create(
            {"name": "Other Inventory Company"}
        )
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Other Inventory Warehouse",
                "code": "OIWH",
                "company_id": other_company.id,
            }
        )
        other_order = (
            self.env["sedar.marine.service.order"]
            .sudo()
            .with_company(other_company)
            .create(
                {
                    "company_id": other_company.id,
                    "client_id": self.partner.id,
                    "assisted_vessel_name": "MV Other Inventory Company",
                    "service_type_id": self.service.id,
                    "number_of_tugs": 1,
                    "scope_of_work": "Company isolation test.",
                    "port_id": self.port.id,
                    "requested_start": datetime(2026, 9, 7, 8, 0, 0),
                    "estimated_duration_hours": 2,
                    "state": "planning",
                }
            )
        )

        self.assertFalse(other_order._find_inventory_template())
        requirement = (
            self.env["sedar.inventory.requirement"]
            .sudo()
            .create(
                {
                    "order_id": other_order.id,
                    "product_id": self.product.id,
                    "source_location_id": other_warehouse.lot_stock_id.id,
                    "required_qty": 1,
                }
            )
        )
        self.assertEqual(requirement.company_id, other_company)
        self.assertFalse(
            self.env["sedar.inventory.requirement"]
            .with_user(self.inventory_manager)
            .search([("id", "=", requirement.id)])
        )

        main_order = self._make_order()
        with self.assertRaises(ValidationError):
            self.env["sedar.inventory.requirement"].sudo().create(
                {
                    "order_id": main_order.id,
                    "product_id": self.product.id,
                    "source_location_id": other_warehouse.lot_stock_id.id,
                    "required_qty": 1,
                }
            )

    def test_inventory_template_requires_company_owned_source_location(self):
        shared_parent = self.env["stock.location"].search(
            [
                ("usage", "=", "view"),
                ("company_id", "=", False),
            ],
            limit=1,
        )
        shared_location = self.env["stock.location"].create(
            {
                "name": "Ambiguous Inventory Source",
                "usage": "internal",
                "location_id": shared_parent.id,
                "company_id": False,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["sedar.inventory.template"].create(
                {
                    "name": "Ambiguous Template",
                    "service_type_id": self.service.id,
                    "source_location_id": shared_location.id,
                }
            )

    def test_inventory_template_source_change_revalidates_existing_products(self):
        company_product = self.env["product.product"].create(
            {
                "name": "Company-owned Template Product",
                "type": "consu",
                "is_storable": True,
                "company_id": self.company.id,
            }
        )
        template = self.env["sedar.inventory.template"].create(
            {
                "name": "Company-owned Product Template",
                "service_type_id": self.service.id,
                "source_location_id": self.stock_location.id,
                "line_ids": [
                    Command.create(
                        {
                            "product_id": company_product.id,
                            "required_qty": 1,
                        }
                    )
                ],
            }
        )
        other_company = self.env["res.company"].create(
            {
                "name": "Template Reparenting Other Company",
            }
        )
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Template Reparenting Other Warehouse",
                "code": "TRWH",
                "company_id": other_company.id,
            }
        )

        with self.assertRaisesRegex(ValidationError, "conflicts"):
            template.write({"source_location_id": other_warehouse.lot_stock_id.id})

        self.assertEqual(template.company_id, self.company)

    def test_fuel_log_inherits_operation_company(self):
        fuel_log = self.env.ref("sedar_marine_inventory.fuel_completed_operation")

        self.assertEqual(fuel_log.company_id, fuel_log.operation_id.company_id)
        self.assertTrue(fuel_log._fields["stock_move_ids"].check_company)

    def test_service_order_migration_infers_company_from_fuel_locations(self):
        migration_path = (
            Path(get_module_path("sedar_marine_operations"))
            / "migrations/19.0.2.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_service_order_fuel_company_migration", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        other_company = self.env["res.company"].create(
            {"name": "Fuel Evidence Company"}
        )
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Fuel Evidence Warehouse",
                "code": "FEWH",
                "company_id": other_company.id,
            }
        )
        other_tug = (
            self.env["sedar.tugboat"]
            .sudo()
            .with_company(other_company)
            .create(
                {
                    "name": "Fuel Evidence Tug",
                    "registration_number": "FUEL-EVIDENCE-TUG",
                    "tug_class_id": self.tug_class.id,
                    "company_id": other_company.id,
                }
            )
        )
        tug_location = self.env["stock.location"].create(
            {
                "name": "Fuel Evidence Tug Tank",
                "usage": "internal",
                "location_id": other_warehouse.view_location_id.id,
                "company_id": other_company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": other_tug.id,
            }
        )
        other_tug.stock_location_id = tug_location
        order = (
            self.env["sedar.marine.service.order"]
            .with_company(other_company)
            .create(
                {
                    "company_id": other_company.id,
                    "client_id": self.partner.id,
                    "assisted_vessel_name": "MV Fuel Evidence",
                    "service_type_id": self.service.id,
                    "scope_of_work": "Fuel-location migration evidence test.",
                    "port_id": self.port.id,
                    "requested_start": datetime(2026, 9, 8, 9, 0, 0),
                }
            )
        )
        operation = (
            self.env["sedar.marine.operation"]
            .with_company(other_company)
            .create({"order_id": order.id})
        )
        self.env["sedar.operation.fuel.log"].with_company(other_company).create(
            {
                "operation_id": operation.id,
                "tugboat_id": other_tug.id,
                "product_id": self.product.id,
                "source_location_id": other_warehouse.lot_stock_id.id,
                "tug_location_id": tug_location.id,
            }
        )
        self.env.cr.execute(
            "ALTER TABLE sedar_marine_service_order "
            "ALTER COLUMN company_id DROP NOT NULL"
        )
        self.env.cr.execute(
            "UPDATE sedar_marine_service_order SET company_id = NULL WHERE id = %s",
            (order.id,),
        )

        migration.migrate(self.env.cr, "19.0.1.0.0")

        order.invalidate_recordset(["company_id"])
        self.assertEqual(order.company_id, other_company)

    def test_fuel_moves_use_operation_company_when_another_company_is_active(self):
        other_company = self.env["res.company"].create({"name": "Other Fuel Company"})
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Other Fuel Warehouse",
                "code": "OFWH",
                "company_id": other_company.id,
            }
        )
        other_warehouse.lot_stock_id.sedar_location_role = "storage"
        other_tug = (
            self.env["sedar.tugboat"]
            .sudo()
            .with_company(other_company)
            .create(
                {
                    "name": "Other Company Fuel Tug",
                    "registration_number": "OTHER-FUEL-TUG",
                    "tug_class_id": self.tug_class.id,
                    "company_id": other_company.id,
                }
            )
        )
        tug_location = self.env["stock.location"].create(
            {
                "name": "Other Company Tug Tank",
                "usage": "internal",
                "location_id": other_warehouse.view_location_id.id,
                "company_id": other_company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": other_tug.id,
            }
        )
        other_tug.stock_location_id = tug_location
        consumption = self.env["stock.location"].create(
            {
                "name": "Other Company Fuel Consumption",
                "usage": "inventory",
                "location_id": other_warehouse.view_location_id.id,
                "company_id": other_company.id,
                "sedar_location_role": "consumption",
            }
        )
        officer = self.env["res.users"].create(
            {
                "name": "Other Company Fuel Officer",
                "login": "other.company.fuel.officer@test.example",
                "company_id": self.company.id,
                "company_ids": [Command.set([self.company.id, other_company.id])],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "sedar_marine_inventory.group_marine_inventory_manager"
                            ).id,
                        ]
                    )
                ],
            }
        )
        other_company.write(
            {
                "sedar_procurement_inventory_officer_id": officer.id,
                "sedar_default_storage_location_id": other_warehouse.lot_stock_id.id,
                "sedar_consumption_location_id": consumption.id,
            }
        )
        other_order = (
            self.env["sedar.marine.service.order"]
            .with_company(other_company)
            .create(
                {
                    "company_id": other_company.id,
                    "client_id": self.partner.id,
                    "assisted_vessel_name": "MV Other Fuel Company",
                    "service_type_id": self.service.id,
                    "scope_of_work": "Fuel company-context test.",
                    "port_id": self.port.id,
                    "requested_start": datetime(2026, 9, 8, 8, 0, 0),
                }
            )
        )
        operation = (
            self.env["sedar.marine.operation"]
            .with_company(other_company)
            .create(
                {
                    "order_id": other_order.id,
                }
            )
        )
        self.env["stock.quant"].with_company(other_company)._update_available_quantity(
            self.product,
            other_warehouse.lot_stock_id,
            20,
        )
        self.product.write(
            {
                "default_code": "OTHER-COMPANY-FUEL",
                "sedar_inventory_item": True,
                "sedar_item_type": "fuel_lubricant",
            }
        )
        fuel_log = (
            self.env["sedar.operation.fuel.log"]
            .with_company(other_company)
            .create(
                {
                    "operation_id": operation.id,
                    "tugboat_id": other_tug.id,
                    "product_id": self.product.id,
                    "source_location_id": other_warehouse.lot_stock_id.id,
                    "tug_location_id": tug_location.id,
                    "quantity_to_issue": 10,
                    "quantity_to_consume": 4,
                }
            )
        )

        self.assertEqual(fuel_log.env.company, other_company)
        fuel_log.with_user(officer).with_company(self.company).action_issue_to_tug()
        fuel_log.with_user(officer).with_company(
            self.company
        ).action_record_consumption()

        self.assertEqual(fuel_log.stock_move_ids.mapped("company_id"), other_company)
        consumption_move = fuel_log.stock_move_ids.filtered(
            lambda move: move.location_dest_id.usage == "inventory"
        )
        self.assertEqual(consumption_move.location_dest_id.company_id, other_company)

    def test_inventory_template_upgrade_rejects_ambiguous_source_company(self):
        migration_path = (
            Path(get_module_path("sedar_marine_inventory"))
            / "migrations/19.0.2.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_marine_inventory_pre_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        self.env.cr.execute(
            "UPDATE stock_location SET company_id = NULL WHERE id = %s",
            [self.stock_location.id],
        )
        with self.assertRaisesRegex(RuntimeError, "company-owned source locations"):
            migration.migrate(self.env.cr, "19.0.1.0.0")
        self.env.cr.execute(
            "UPDATE stock_location SET company_id = %s WHERE id = %s",
            [self.company.id, self.stock_location.id],
        )
        migration.migrate(self.env.cr, "19.0.1.0.0")
        migration.migrate(self.env.cr, "19.0.1.0.0")

    def test_inventory_upgrade_rejects_cross_company_requirement_product(self):
        migration_path = (
            Path(get_module_path("sedar_marine_inventory"))
            / "migrations/19.0.2.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_inventory_requirement_pre_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        other_company = self.env["res.company"].create(
            {"name": "Requirement Migration Company"}
        )
        product = self.env["product.product"].create(
            {
                "name": "Requirement Migration Product",
                "type": "consu",
                "is_storable": True,
            }
        )
        order = self._make_order()
        requirement = self.env["sedar.inventory.requirement"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "source_location_id": self.stock_location.id,
                "required_qty": 1,
            }
        )
        self.env.cr.execute(
            "UPDATE product_template SET company_id = %s WHERE id = %s",
            (other_company.id, product.product_tmpl_id.id),
        )

        with self.assertRaisesRegex(RuntimeError, "Inventory Requirement products"):
            migration.migrate(self.env.cr, "19.0.1.0.0")

        self.env.cr.execute(
            "UPDATE product_template SET company_id = NULL WHERE id = %s",
            (product.product_tmpl_id.id,),
        )
        requirement.invalidate_recordset()

    def test_inventory_upgrade_rejects_cross_company_fuel_location(self):
        migration_path = (
            Path(get_module_path("sedar_marine_inventory"))
            / "migrations/19.0.2.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_inventory_fuel_pre_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        other_company = self.env["res.company"].create(
            {"name": "Fuel Migration Company"}
        )
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Fuel Migration Warehouse",
                "code": "FMWH",
                "company_id": other_company.id,
            }
        )
        fuel_log = self.env.ref("sedar_marine_inventory.fuel_completed_operation")
        original_location = fuel_log.source_location_id
        self.env.cr.execute(
            "UPDATE sedar_operation_fuel_log SET source_location_id = %s WHERE id = %s",
            (other_warehouse.lot_stock_id.id, fuel_log.id),
        )

        with self.assertRaisesRegex(RuntimeError, "Fuel-log products or locations"):
            migration.migrate(self.env.cr, "19.0.1.0.0")

        self.env.cr.execute(
            "UPDATE sedar_operation_fuel_log SET source_location_id = %s WHERE id = %s",
            (original_location.id, fuel_log.id),
        )
        fuel_log.invalidate_recordset(["source_location_id"])

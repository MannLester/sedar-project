import importlib.util
from pathlib import Path
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInventoryLifecycleEdges(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.storage = cls.warehouse.lot_stock_id
        cls.storage.sedar_location_role = "storage"
        cls.virtual = cls.env["stock.location"].search(
            [
                ("usage", "=", "view"),
                ("company_id", "in", [False, cls.company.id]),
            ],
            order="company_id desc, id",
            limit=1,
        )
        cls.consumption = cls.env["stock.location"].create(
            {
                "name": "Edge Test Consumption",
                "usage": "inventory",
                "location_id": cls.virtual.id,
                "company_id": cls.company.id,
                "sedar_location_role": "consumption",
            }
        )
        cls.disposal = cls.env["stock.location"].create(
            {
                "name": "Edge Test Disposal",
                "usage": "inventory",
                "location_id": cls.virtual.id,
                "company_id": cls.company.id,
                "sedar_location_role": "disposal",
            }
        )
        cls.tug_class = cls.env["sedar.tug.class"].create(
            {"name": "Lifecycle Edge Tug Class"}
        )
        cls.tug = cls.env["sedar.tugboat"].create(
            {
                "name": "Lifecycle Edge Tug",
                "registration_number": "LIFECYCLE-EDGE-TUG",
                "tug_class_id": cls.tug_class.id,
                "company_id": cls.company.id,
            }
        )
        cls.tug_location = cls.env["stock.location"].create(
            {
                "name": "Lifecycle Edge Tug Stock",
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
        cls.officer = cls.env["res.users"].create(
            {
                "name": "Lifecycle Edge Officer",
                "login": "lifecycle.edge.officer@test.example",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [
                    Command.set(
                        [cls.env.ref("base.group_user").id, inventory_group.id]
                    )
                ],
            }
        )
        cls.company.write(
            {
                "sedar_procurement_inventory_officer_id": cls.officer.id,
                "sedar_default_storage_location_id": cls.storage.id,
                "sedar_consumption_location_id": cls.consumption.id,
                "sedar_disposal_location_id": cls.disposal.id,
            }
        )
        cls.product = cls._create_product("Lifecycle Edge Spare", "EDGE-SPARE")
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.storage, 50
        )

    @classmethod
    def _create_product(cls, name, code, **values):
        product_values = {
            "name": name,
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.unit.id,
            "default_code": code,
            "sedar_inventory_item": True,
            "sedar_item_type": "spare_consumable",
        }
        product_values.update(values)
        return cls.env["product.product"].create(product_values)

    def _issue(self, quantity, product=None, lot=None, source=None):
        return (
            self.env["sedar.inventory.issue"]
            .with_user(self.officer)
            ._issue_to_tug(
                product or self.product,
                self.tug,
                quantity,
                "Inventory lifecycle edge test",
                source or self.storage,
                lot,
            )
        )

    def _load_migration(self):
        migration_path = (
            Path(get_module_path("sedar_marine_inventory"))
            / "migrations/19.0.3.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_inventory_lifecycle_edge_migration", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        return migration

    def _create_legacy_issue(self, move):
        return (
            self.env["sedar.inventory.issue"]
            .sudo()
            .with_context(sedar_inventory_issue_create=True)
            .create(
                {
                    "name": "LEGACY-EDGE",
                    "company_id": self.company.id,
                    "product_id": self.product.id,
                    "tugboat_id": self.tug.id,
                    "source_location_id": self.storage.id,
                    "tug_location_id": self.tug_location.id,
                    "quantity": 2,
                    "purpose": "Legacy migration edge test",
                    "issued_by_id": self.officer.id,
                    "issued_at": fields.Datetime.now(),
                    "stock_move_id": move.id,
                }
            )
        )

    def test_uom_rounding_rejects_a_sub_rounding_disposition(self):
        lifecycle = self._issue(1).lifecycle_id.with_user(self.officer)

        below_rounding = self.product.uom_id.rounding / 10
        with self.assertRaises(UserError):
            lifecycle.action_consume(below_rounding, "Below unit rounding")

        self.assertEqual(lifecycle.open_qty, 1)
        self.assertFalse(lifecycle.event_ids)

    def test_reserved_stock_is_not_available_to_issue(self):
        reserve_destination = self.env["stock.location"].create(
            {
                "name": "Reserved Stock Destination",
                "usage": "internal",
                "location_id": self.storage.location_id.id,
                "company_id": self.company.id,
            }
        )
        reserved_move = self.env["stock.move"].create(
            {
                "origin": "Reserve lifecycle edge stock",
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom_qty": 45,
                "product_uom": self.product.uom_id.id,
                "location_id": self.storage.id,
                "location_dest_id": reserve_destination.id,
            }
        )
        reserved_move._action_confirm()
        reserved_move._action_assign()

        available = self.env["sedar.inventory.lifecycle"]._available_quantity(
            self.product, self.storage
        )
        self.assertEqual(available, 5)
        with self.assertRaises(UserError):
            self._issue(6)

        issue = self._issue(5)
        self.assertEqual(issue.quantity, 5)

    def test_issue_failure_rolls_back_the_completed_stock_move(self):
        lifecycle_model = self.env["sedar.inventory.lifecycle"]
        model_class = type(lifecycle_model)
        original_create = model_class.create
        move_count = self.env["stock.move"].search_count(
            [("product_id", "=", self.product.id)]
        )
        available = lifecycle_model._available_quantity(self.product, self.storage)

        def fail_lifecycle_create(records, values):
            if records.env.context.get("sedar_inventory_lifecycle_create"):
                raise UserError("Injected lifecycle creation failure")
            return original_create(records, values)

        with self.assertRaises(UserError), self.env.cr.savepoint(), patch.object(
            model_class, "create", fail_lifecycle_create
        ):
            self._issue(3)

        self.assertEqual(
            self.env["stock.move"].search_count(
                [("product_id", "=", self.product.id)]
            ),
            move_count,
        )
        self.assertEqual(
            lifecycle_model._available_quantity(self.product, self.storage), available
        )

    def test_lifecycle_record_rules_hide_other_company_records(self):
        other_company = self.env["res.company"].create({"name": "Edge Other Company"})
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Edge Other Warehouse",
                "code": "EOWH",
                "company_id": other_company.id,
            }
        )
        other_storage = other_warehouse.lot_stock_id
        other_storage.sedar_location_role = "storage"
        other_tug = (
            self.env["sedar.tugboat"]
            .sudo()
            .with_company(other_company)
            .create(
                {
                    "name": "Edge Other Tug",
                    "registration_number": "EDGE-OTHER-TUG",
                    "tug_class_id": self.tug_class.id,
                    "company_id": other_company.id,
                }
            )
        )
        other_tug_location = self.env["stock.location"].create(
            {
                "name": "Edge Other Tug Stock",
                "usage": "internal",
                "location_id": other_warehouse.view_location_id.id,
                "company_id": other_company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": other_tug.id,
            }
        )
        other_tug.stock_location_id = other_tug_location
        inventory_group = self.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        other_officer = self.env["res.users"].create(
            {
                "name": "Edge Other Officer",
                "login": "lifecycle.edge.other.officer@test.example",
                "company_id": other_company.id,
                "company_ids": [Command.set(other_company.ids)],
                "group_ids": [
                    Command.set(
                        [self.env.ref("base.group_user").id, inventory_group.id]
                    )
                ],
            }
        )
        other_company.write(
            {
                "sedar_procurement_inventory_officer_id": other_officer.id,
                "sedar_default_storage_location_id": other_storage.id,
            }
        )
        self.env["stock.quant"].with_company(
            other_company
        )._update_available_quantity(self.product, other_storage, 2)
        other_issue = (
            self.env["sedar.inventory.issue"]
            .with_user(other_officer)
            .with_company(other_company)
            ._issue_to_tug(
                self.product,
                other_tug,
                1,
                "Other-company visibility test",
                other_storage,
            )
        )

        visible_ids = (
            self.env["sedar.inventory.lifecycle"]
            .with_user(self.officer)
            .search([])
            .ids
        )
        event_visible_ids = (
            self.env["sedar.inventory.lifecycle.event"]
            .with_user(self.officer)
            .search([])
            .ids
        )
        self.assertNotIn(other_issue.lifecycle_id.id, visible_ids)
        self.assertFalse(
            set(other_issue.lifecycle_id.event_ids.ids).intersection(event_visible_ids)
        )

    def test_storage_projection_aggregates_multiple_warehouses(self):
        second_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Edge Second Warehouse",
                "code": "ESWH",
                "company_id": self.company.id,
            }
        )
        second_storage = second_warehouse.lot_stock_id
        second_storage.sedar_location_role = "storage"
        aggregate_product = self._create_product(
            "Multiwarehouse Edge Spare", "EDGE-MULTIWAREHOUSE"
        )
        self.env["stock.quant"]._update_available_quantity(
            aggregate_product, self.storage, 4
        )
        self.env["stock.quant"]._update_available_quantity(
            aggregate_product, second_storage, 7
        )
        aggregate_product.invalidate_recordset(
            [
                "sedar_on_hand_qty",
                "sedar_reserved_qty",
                "sedar_available_to_issue",
            ]
        )

        self.assertEqual(aggregate_product.sedar_on_hand_qty, 11)
        self.assertEqual(aggregate_product.sedar_available_to_issue, 11)

    def test_open_replacement_serial_cannot_have_two_lifecycles(self):
        replacement = self._create_product(
            "Serialized Edge Pump",
            "EDGE-SERIAL-PUMP",
            tracking="serial",
            sedar_item_type="replacement_equipment",
        )
        serial = self.env["stock.lot"].create(
            {
                "name": "EDGE-SERIAL-001",
                "product_id": replacement.id,
                "company_id": self.company.id,
            }
        )
        self.env["stock.quant"]._update_available_quantity(
            replacement, self.storage, 1, lot_id=serial
        )
        first = self._issue(1, replacement, serial).lifecycle_id
        self.env["stock.quant"]._update_available_quantity(
            replacement, self.storage, 1, lot_id=serial
        )

        with self.assertRaises(ValidationError):
            self._issue(1, replacement, serial)

        self.assertEqual(first.state, "open")

    def test_lifecycle_rejects_a_completed_move_with_the_wrong_endpoint(self):
        wrong_destination = self.env["stock.location"].create(
            {
                "name": "Wrong Lifecycle Endpoint",
                "usage": "internal",
                "location_id": self.storage.location_id.id,
                "company_id": self.company.id,
            }
        )
        move = self.env["sedar.inventory.lifecycle"]._create_done_stock_move(
            self.product,
            2,
            self.storage,
            wrong_destination,
            "Wrong endpoint edge test",
            self.company,
        )
        issue = self._create_legacy_issue(move)

        with self.assertRaises(ValidationError):
            (
                self.env["sedar.inventory.lifecycle"]
                .sudo()
                .with_context(sedar_inventory_lifecycle_create=True)
                .create(
                    {
                        "issue_id": issue.id,
                        "company_id": self.company.id,
                        "product_id": self.product.id,
                        "product_uom_id": self.product.uom_id.id,
                        "tugboat_id": self.tug.id,
                        "source_location_id": self.storage.id,
                        "tug_location_id": self.tug_location.id,
                        "issue_move_id": move.id,
                        "initial_qty": 2,
                        "issued_by_id": self.officer.id,
                        "issued_at": issue.issued_at,
                    }
                )
            )

    def test_legacy_migration_is_idempotent_and_preserves_consumed_move(self):
        move = self.env["sedar.inventory.lifecycle"]._create_done_stock_move(
            self.product,
            2,
            self.storage,
            self.consumption,
            "Valid legacy inventory issue",
            self.company,
        )
        issue = self._create_legacy_issue(move)
        migration = self._load_migration()
        destination = move.location_dest_id

        migration.migrate(self.env.cr, "19.0.2.0.0")
        migration.migrate(self.env.cr, "19.0.2.0.0")

        issue.invalidate_recordset(
            ["company_id", "tug_location_id", "legacy_consumed", "lifecycle_id"]
        )
        move.invalidate_recordset(["state", "location_dest_id"])
        self.assertTrue(issue.legacy_consumed)
        self.assertFalse(issue.lifecycle_id)
        self.assertEqual(issue.company_id, self.company)
        self.assertEqual(issue.tug_location_id, self.tug_location)
        self.assertEqual(move.state, "done")
        self.assertEqual(move.location_dest_id, destination)

    def test_legacy_migration_rejects_anomalous_move_evidence(self):
        move = self.env["stock.move"].create(
            {
                "origin": "Anomalous legacy inventory issue",
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "product_uom": self.product.uom_id.id,
                "location_id": self.storage.id,
                "location_dest_id": self.consumption.id,
            }
        )
        issue = self._create_legacy_issue(move)

        with self.assertRaisesRegex(UserError, str(issue.id)):
            self._load_migration().migrate(self.env.cr, "19.0.2.0.0")

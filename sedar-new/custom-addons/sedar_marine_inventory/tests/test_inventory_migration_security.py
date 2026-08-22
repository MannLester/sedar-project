import importlib.util
from pathlib import Path

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInventoryMigrationSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {"name": "Inventory Migration Security Company"}
        )
        cls.other_company = cls.env["res.company"].create(
            {"name": "Inventory Migration Security Other Company"}
        )
        cls.warehouse = cls.env["stock.warehouse"].create(
            {
                "name": "Inventory Migration Security Warehouse",
                "code": "IMSC",
                "company_id": cls.company.id,
            }
        )
        cls.storage = cls.warehouse.lot_stock_id
        cls.storage.sedar_location_role = "storage"
        cls.virtual_parent = cls.env["stock.location"].search(
            [
                ("usage", "=", "view"),
                ("company_id", "in", [False, cls.company.id]),
            ],
            order="company_id desc, id",
            limit=1,
        )
        cls.consumption = cls.env["stock.location"].create(
            {
                "name": "Inventory Migration Security Consumption",
                "usage": "inventory",
                "location_id": cls.virtual_parent.id,
                "company_id": cls.company.id,
            }
        )
        tug_class = cls.env["sedar.tug.class"].create(
            {"name": "Inventory Migration Security Tug Class"}
        )
        cls.tug = cls.env["sedar.tugboat"].with_company(cls.company).create(
            {
                "name": "Inventory Migration Security Tug",
                "registration_number": "IMSC-TUG",
                "tug_class_id": tug_class.id,
                "company_id": cls.company.id,
            }
        )
        cls.tug_location = cls.env["stock.location"].create(
            {
                "name": "Inventory Migration Security Tug Stock",
                "usage": "internal",
                "location_id": cls.warehouse.view_location_id.id,
                "company_id": cls.company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": cls.tug.id,
            }
        )
        cls.tug.stock_location_id = cls.tug_location
        cls.product = cls.env["product.product"].create(
            {
                "name": "Inventory Migration Security Spare",
                "type": "consu",
                "is_storable": True,
                "default_code": "IMSC-SPARE",
                "sedar_inventory_item": True,
                "sedar_item_type": "spare_consumable",
            }
        )
        cls.env["stock.quant"].with_company(cls.company)._update_available_quantity(
            cls.product, cls.storage, 20
        )
        cls.actor = cls.env["res.users"].create(
            {
                "name": "Inventory Migration Security Actor",
                "login": "inventory.migration.security.actor@test.example",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
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

    @classmethod
    def _load_migration(cls):
        migration_path = (
            Path(get_module_path("sedar_marine_inventory"))
            / "migrations/19.0.3.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_inventory_migration_security", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        return migration

    def _create_legacy_issue(self, destination=None):
        destination = destination or self.consumption
        move = self.env["sedar.inventory.lifecycle"]._create_done_stock_move(
            self.product,
            1,
            self.storage,
            destination,
            "Inventory migration security legacy issue",
            self.company,
        )
        issue = (
            self.env["sedar.inventory.issue"]
            .sudo()
            .with_context(sedar_inventory_issue_create=True)
            .create(
                {
                    "name": "IMSC-LEGACY-%s" % move.id,
                    "company_id": self.company.id,
                    "product_id": self.product.id,
                    "tugboat_id": self.tug.id,
                    "source_location_id": self.storage.id,
                    "tug_location_id": self.tug_location.id,
                    "quantity": 1,
                    "purpose": "Inventory migration security test",
                    "issued_by_id": self.actor.id,
                    "issued_at": fields.Datetime.now(),
                    "stock_move_id": move.id,
                }
            )
        )
        return issue, move

    def test_maintenance_part_rule_is_global_and_company_scoped(self):
        other_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Inventory Security Other Warehouse",
                "code": "ISOW",
                "company_id": self.other_company.id,
            }
        )
        self.storage.sedar_location_role = "storage"
        other_warehouse.lot_stock_id.sedar_location_role = "storage"
        team_a = self.env["maintenance.team"].create(
            {
                "name": "Company A Inventory Security Team",
                "company_id": self.company.id,
            }
        )
        team_b = self.env["maintenance.team"].create(
            {
                "name": "Company B Inventory Security Team",
                "company_id": self.other_company.id,
            }
        )
        request_a = self.env["maintenance.request"].with_company(self.company).create(
            {
                "name": "Company A inventory security work order",
                "company_id": self.company.id,
                "maintenance_team_id": team_a.id,
                "maintenance_type": "corrective",
                "sedar_work_order_type": "defect",
                "sedar_defect_source": "Company-rule test",
            }
        )
        request_b = self.env["maintenance.request"].with_company(
            self.other_company
        ).create(
            {
                "name": "Company B inventory security work order",
                "company_id": self.other_company.id,
                "maintenance_team_id": team_b.id,
                "maintenance_type": "corrective",
                "sedar_work_order_type": "defect",
                "sedar_defect_source": "Company-rule test",
            }
        )
        line_a = self.env["sedar.maintenance.part.line"].create(
            {
                "maintenance_request_id": request_a.id,
                "product_id": self.product.id,
                "source_location_id": self.storage.id,
                "requested_qty": 1,
            }
        )
        line_b = self.env["sedar.maintenance.part.line"].with_company(
            self.other_company
        ).create(
            {
                "maintenance_request_id": request_b.id,
                "product_id": self.product.id,
                "source_location_id": other_warehouse.lot_stock_id.id,
                "requested_qty": 1,
            }
        )
        maintenance_user = self.env["res.users"].create(
            {
                "name": "Company A Maintenance User",
                "login": "company.a.maintenance.security@test.example",
                "company_id": self.company.id,
                "company_ids": [Command.set(self.company.ids)],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "sedar_marine_maintenance.group_marine_maintenance_user"
                            ).id,
                        ]
                    )
                ],
            }
        )

        visible = self.env["sedar.maintenance.part.line"].with_user(
            maintenance_user
        ).search([])

        self.assertIn(line_a, visible)
        self.assertNotIn(line_b, visible)
        with self.assertRaises(AccessError):
            line_b.with_user(maintenance_user).write({"note": "Cross-company edit"})

    def test_migration_rejects_move_source_company_mismatch_with_issue_id(self):
        issue, move = self._create_legacy_issue()
        self.env.cr.execute(
            "UPDATE stock_move SET company_id = %s WHERE id = %s",
            (self.other_company.id, move.id),
        )

        with self.assertRaisesRegex(UserError, str(issue.id)):
            self._load_migration().migrate(self.env.cr, "19.0.2.0.0")

    def test_migration_rejects_shared_and_foreign_destinations_with_issue_ids(self):
        shared_destination = self.env["stock.location"].create(
            {
                "name": "Inventory Migration Shared Destination",
                "usage": "inventory",
                "location_id": self.virtual_parent.id,
                "company_id": self.company.id,
            }
        )
        foreign_destination = self.env["stock.location"].create(
            {
                "name": "Inventory Migration Foreign Destination",
                "usage": "inventory",
                "location_id": self.virtual_parent.id,
                "company_id": self.company.id,
            }
        )
        shared_issue, _shared_move = self._create_legacy_issue(shared_destination)
        foreign_issue, _foreign_move = self._create_legacy_issue(foreign_destination)
        self.env.cr.execute(
            "UPDATE stock_location SET company_id = NULL WHERE id = %s",
            [shared_destination.id],
        )
        self.env.cr.execute(
            "UPDATE stock_location SET company_id = %s WHERE id = %s",
            (self.other_company.id, foreign_destination.id),
        )

        with self.assertRaisesRegex(
            UserError, rf"{shared_issue.id}.*{foreign_issue.id}"
        ):
            self._load_migration().migrate(self.env.cr, "19.0.2.0.0")

    def test_migration_rejects_foreign_tug_and_tug_location_with_issue_id(self):
        issue, _move = self._create_legacy_issue()
        migration = self._load_migration()
        self.env.cr.execute(
            "UPDATE sedar_tugboat SET company_id = %s WHERE id = %s",
            (self.other_company.id, self.tug.id),
        )

        with self.assertRaisesRegex(UserError, str(issue.id)):
            migration.migrate(self.env.cr, "19.0.2.0.0")

        self.env.cr.execute(
            "UPDATE sedar_tugboat SET company_id = %s WHERE id = %s",
            (self.company.id, self.tug.id),
        )
        self.env.cr.execute(
            "UPDATE stock_location SET company_id = %s WHERE id = %s",
            (self.other_company.id, self.tug_location.id),
        )

        with self.assertRaisesRegex(UserError, str(issue.id)):
            migration.migrate(self.env.cr, "19.0.2.0.0")

    def test_valid_migration_is_idempotent_and_preserves_the_done_move(self):
        issue, move = self._create_legacy_issue()
        destination = move.location_dest_id

        migration = self._load_migration()
        migration.migrate(self.env.cr, "19.0.2.0.0")
        migration.migrate(self.env.cr, "19.0.2.0.0")

        issue.invalidate_recordset(
            ["company_id", "tug_location_id", "legacy_consumed", "lifecycle_id"]
        )
        move.invalidate_recordset(["state", "location_dest_id"])
        destination.invalidate_recordset(["company_id", "sedar_location_role"])
        self.assertTrue(issue.legacy_consumed)
        self.assertFalse(issue.lifecycle_id)
        self.assertEqual(issue.company_id, self.company)
        self.assertEqual(issue.tug_location_id, self.tug_location)
        self.assertEqual(move.state, "done")
        self.assertEqual(move.location_dest_id, destination)
        self.assertEqual(destination.company_id, self.company)
        self.assertEqual(destination.sedar_location_role, "consumption")

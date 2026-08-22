from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInventoryLifecycle(TransactionCase):
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
        cls.consumption = cls.env["stock.location"].create({
            "name": "Lifecycle Consumption",
            "usage": "inventory",
            "location_id": virtual.id,
            "company_id": cls.company.id,
            "sedar_location_role": "consumption",
        })
        cls.disposal = cls.env["stock.location"].create({
            "name": "Lifecycle Disposal",
            "usage": "inventory",
            "location_id": virtual.id,
            "company_id": cls.company.id,
            "sedar_location_role": "disposal",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Lifecycle Tug Class"})
        tug_values = {
            "name": "Lifecycle Tug",
            "registration_number": "LIFECYCLE-TUG",
            "tug_class_id": cls.tug_class.id,
        }
        if "company_id" in cls.env["sedar.tugboat"]:
            tug_values["company_id"] = cls.company.id
        cls.tug = cls.env["sedar.tugboat"].create(tug_values)
        cls.tug_location = cls.env["stock.location"].create({
            "name": "Lifecycle Tug Stock",
            "usage": "internal",
            "location_id": cls.storage.location_id.id,
            "company_id": cls.company.id,
            "sedar_location_role": "tug",
            "sedar_tugboat_id": cls.tug.id,
        })
        cls.tug.stock_location_id = cls.tug_location
        inventory_group = cls.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        maintenance_group = cls.env.ref(
            "sedar_marine_maintenance.group_marine_maintenance_manager"
        )
        cls.officer = cls.env["res.users"].create({
            "name": "Exact Lifecycle Officer",
            "login": "exact.lifecycle.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                inventory_group.id,
            ])],
        })
        cls.other_officer = cls.env["res.users"].create({
            "name": "Other Lifecycle Officer",
            "login": "other.lifecycle.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                inventory_group.id,
            ])],
        })
        cls.maintenance_manager = cls.env["res.users"].create({
            "name": "Lifecycle Maintenance Manager",
            "login": "lifecycle.maintenance@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                maintenance_group.id,
            ])],
        })
        cls.company.write({
            "sedar_procurement_inventory_officer_id": cls.officer.id,
            "sedar_default_storage_location_id": cls.storage.id,
            "sedar_consumption_location_id": cls.consumption.id,
            "sedar_disposal_location_id": cls.disposal.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Lifecycle Spare",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.unit.id,
            "default_code": "LIFECYCLE-SPARE",
            "sedar_inventory_item": True,
            "sedar_item_type": "spare_consumable",
        })
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.storage, 100
        )

    def _issue(self, quantity=10, product=None, lot=None):
        product = product or self.product
        return self.env["sedar.inventory.issue"].with_user(self.officer)._issue_to_tug(
            product,
            self.tug,
            quantity,
            "Lifecycle test issue",
            self.storage,
            lot,
        )

    def test_issue_moves_storage_to_tug_and_creates_open_lifecycle(self):
        issue = self._issue()

        self.assertEqual(issue.stock_move_id.state, "done")
        self.assertEqual(issue.stock_move_id.location_id, self.storage)
        self.assertEqual(issue.stock_move_id.location_dest_id, self.tug_location)
        self.assertEqual(issue.lifecycle_id.open_qty, 10)
        self.assertEqual(issue.lifecycle_id.state, "open")
        self.assertEqual(issue.lifecycle_id.usage_state, "onboard")
        self.assertEqual(issue.lifecycle_id.reconciliation_state, "reconciled")

    def test_partial_mixed_closes_have_explicit_done_moves(self):
        lifecycle = self._issue().lifecycle_id.with_user(self.officer)

        lifecycle.action_return(3, "Unused stock returned")
        lifecycle.action_consume(2, "Used during maintenance")
        lifecycle.action_dispose(5, "Damaged beyond repair")

        self.assertEqual(lifecycle.open_qty, 0)
        self.assertEqual(lifecycle.state, "closed")
        self.assertEqual(lifecycle.usage_state, "closed")
        self.assertEqual(
            lifecycle.event_ids.mapped("event_type"), ["return", "consume", "dispose"]
        )
        self.assertEqual(set(lifecycle.event_ids.mapped("stock_move_id.state")), {"done"})
        self.assertEqual(
            set(lifecycle.event_ids.mapped("stock_move_id.location_dest_id")),
            {self.storage, self.consumption, self.disposal},
        )

    def test_exact_officer_and_over_close_are_enforced_server_side(self):
        lifecycle = self._issue().lifecycle_id

        with self.assertRaises(AccessError):
            lifecycle.with_user(self.other_officer).action_consume(1, "Not authorized")
        with self.assertRaises(UserError):
            lifecycle.with_user(self.officer).action_consume(11, "Too much")
        with self.assertRaises(UserError):
            lifecycle.with_user(self.officer).action_consume(1, "")

    def test_duplicate_consumption_after_close_is_rejected(self):
        lifecycle = self._issue(quantity=1).lifecycle_id.with_user(self.officer)
        lifecycle.action_consume(1, "Consumed once")

        with self.assertRaises(UserError):
            lifecycle.action_consume(1, "Consumed twice")
        self.assertEqual(len(lifecycle.event_ids), 1)

    def test_item_type_and_audit_records_are_immutable(self):
        lifecycle = self._issue().lifecycle_id
        equipment = self.env["maintenance.equipment"].create({
            "name": "Unlinked Equipment Without Inventory Provenance",
            "company_id": self.company.id,
        })

        with self.assertRaises(UserError):
            self.product.write({"sedar_item_type": "fuel_lubricant"})
        with self.assertRaisesRegex(AccessError, "provenance is immutable"):
            equipment.write({"sedar_inventory_product_id": self.product.id})
        with self.assertRaises(AccessError):
            lifecycle.write({"usage_state": "assigned"})
        with self.assertRaises(AccessError):
            lifecycle.unlink()
        lifecycle.with_user(self.maintenance_manager).action_assign()
        event = lifecycle.event_ids
        with self.assertRaises(AccessError):
            event.write({"reason": "Changed"})
        with self.assertRaises(AccessError):
            event.unlink()

    def test_location_roles_and_company_configuration_are_validated(self):
        tug_values = {
            "name": "Invalid Location Tug",
            "registration_number": "INVALID-LOCATION-TUG",
            "tug_class_id": self.tug_class.id,
        }
        if "company_id" in self.env["sedar.tugboat"]:
            tug_values["company_id"] = self.company.id
        other_tug = self.env["sedar.tugboat"].create(tug_values)
        with self.assertRaises(ValidationError):
            self.env["stock.location"].create({
                "name": "Invalid Tug Location",
                "usage": "inventory",
                "location_id": self.storage.location_id.id,
                "company_id": self.company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": other_tug.id,
            })
        with self.assertRaises(ValidationError):
            self.company.sedar_disposal_location_id = self.consumption

    def test_serial_install_remove_and_reinstall_preserve_equipment_identity(self):
        replacement = self.env["product.product"].create({
            "name": "Serialized Replacement Pump",
            "type": "consu",
            "is_storable": True,
            "tracking": "serial",
            "uom_id": self.unit.id,
            "default_code": "LIFECYCLE-PUMP",
            "sedar_inventory_item": True,
            "sedar_item_type": "replacement_equipment",
        })
        serial = self.env["stock.lot"].create({
            "name": "PUMP-SERIAL-001",
            "product_id": replacement.id,
            "company_id": self.company.id,
        })
        self.env["stock.quant"]._update_available_quantity(
            replacement, self.storage, 1, lot_id=serial
        )
        lifecycle = self._issue(1, replacement, serial).lifecycle_id.with_user(
            self.maintenance_manager
        )

        lifecycle.action_install()
        equipment = lifecycle.equipment_id
        self.assertEqual(equipment.sedar_inventory_product_id, replacement)
        self.assertEqual(equipment.sedar_inventory_lot_id, serial)
        self.assertEqual(equipment.sedar_inventory_current_lifecycle_id, lifecycle)
        reading = self.env["sedar.equipment.running.hour.reading"].with_user(
            self.maintenance_manager
        ).create({
            "equipment_id": equipment.id,
            "running_hours": 125,
            "reading_at": fields.Datetime.now(),
        })
        move_count = self.env["stock.move"].search_count([
            ("product_id", "=", replacement.id)
        ])
        physical_before = lifecycle._available_quantity(
            replacement, self.tug_location, serial
        )
        lifecycle.action_remove()

        remove_event = lifecycle.event_ids.filtered(
            lambda event: event.event_type == "remove"
        )
        self.assertFalse(remove_event.stock_move_id)
        self.assertEqual(
            self.env["stock.move"].search_count([
                ("product_id", "=", replacement.id)
            ]),
            move_count,
        )
        self.assertEqual(
            lifecycle._available_quantity(replacement, self.tug_location, serial),
            physical_before,
        )
        self.assertIn(reading, equipment.sedar_running_hour_reading_ids)
        self.assertEqual(equipment.sedar_current_running_hours, 125)
        self.assertFalse(equipment.sedar_tugboat_id)
        self.assertFalse(equipment.sedar_inventory_current_lifecycle_id)
        lifecycle.action_install()

        self.assertEqual(lifecycle.equipment_id, equipment)
        self.assertEqual(equipment.sedar_tugboat_id, self.tug)
        self.assertEqual(equipment.sedar_inventory_current_lifecycle_id, lifecycle)
        self.assertEqual(lifecycle.usage_state, "installed")
        self.assertEqual(lifecycle.event_ids.mapped("event_type"), ["install", "remove", "install"])
        self.assertTrue(lifecycle.disposition_activity_id)

    def test_returned_serial_can_be_reissued_with_same_equipment_identity(self):
        replacement = self.env["product.product"].create({
            "name": "Reissued Replacement Pump",
            "type": "consu",
            "is_storable": True,
            "tracking": "serial",
            "uom_id": self.unit.id,
            "default_code": "REISSUED-PUMP",
            "sedar_inventory_item": True,
            "sedar_item_type": "replacement_equipment",
        })
        serial = self.env["stock.lot"].create({
            "name": "REISSUED-SERIAL-001",
            "product_id": replacement.id,
            "company_id": self.company.id,
        })
        self.env["stock.quant"]._update_available_quantity(
            replacement, self.storage, 1, lot_id=serial
        )
        first = self._issue(1, replacement, serial).lifecycle_id
        first.with_user(self.maintenance_manager).action_install()
        equipment = first.equipment_id
        first.with_user(self.maintenance_manager).action_remove()
        self.assertTrue(first.disposition_activity_id)
        first.with_user(self.officer).action_return(1, "Returned for reassignment")

        second = self._issue(1, replacement, serial).lifecycle_id
        second.with_user(self.maintenance_manager).action_install()

        self.assertNotEqual(first, second)
        self.assertEqual(second.equipment_id, equipment)
        self.assertFalse(first.disposition_activity_id)
        self.assertEqual(equipment.sedar_inventory_current_lifecycle_id, second)

    def test_replacement_equipment_cannot_be_partial_or_unserialized(self):
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({
                "name": "Untracked Replacement",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "default_code": "UNTRACKED-REPLACEMENT",
                "sedar_inventory_item": True,
                "sedar_item_type": "replacement_equipment",
            })

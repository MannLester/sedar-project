from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestInventoryConditionFoundation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.tugboat = cls.env.ref("sedar_service_order_demo.tug_atlas")
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.liter = (
            cls.env.ref("uom.product_uom_litre", raise_if_not_found=False)
            or cls.unit
        )

    def _product(self, code, item_type, uom=None):
        return self.env["product.product"].create({
            "name": code,
            "default_code": code,
            "type": "consu",
            "is_storable": True,
            "uom_id": (uom or self.unit).id,
            "sedar_inventory_item": True,
            "sedar_item_type": item_type,
            "sedar_compatibility_scope": "fleet",
        })

    def test_five_item_categories_are_available(self):
        selection = dict(
            self.env["product.product"]._fields["sedar_item_type"].selection
        )
        self.assertEqual(
            set(selection),
            {
                "fuel_lubricant",
                "consumable_store",
                "spare_part",
                "reusable_onboard_gear",
                "replacement_equipment",
            },
        )

    def test_category_action_contract_is_server_side(self):
        rope = self._product("TEST-ROPE", "reusable_onboard_gear")
        self.assertIn("mark_defective", rope._sedar_allowed_inventory_actions())
        rope._sedar_validate_inventory_action("return_service")
        with self.assertRaises(UserError):
            rope._sedar_validate_inventory_action("consume")

    def test_quantity_uses_uom_rounding(self):
        rope = self._product("TEST-ROUND-ROPE", "reusable_onboard_gear")
        fuel = self._product("TEST-ROUND-FUEL", "fuel_lubricant", self.liter)
        with self.assertRaises(UserError):
            rope._sedar_validate_inventory_quantity(1.5)
        self.assertEqual(rope._sedar_validate_inventory_quantity(2), 2)
        self.assertEqual(fuel._sedar_validate_inventory_quantity(1.5), 1.5)

    def test_bootstrap_configures_condition_locations(self):
        serviceable = self.tugboat.stock_location_id
        quarantine = self.tugboat.quarantine_location_id
        self.assertEqual(serviceable.sedar_location_role, "tug")
        self.assertEqual(quarantine.sedar_location_role, "tug_quarantine")
        self.assertEqual(quarantine.location_id, serviceable)
        self.assertEqual(quarantine.sedar_tugboat_id, self.tugboat)
        warehouse_quarantine = self.company.sedar_quarantine_location_id
        self.assertEqual(
            warehouse_quarantine.sedar_location_role, "storage_quarantine"
        )
        self.assertEqual(
            warehouse_quarantine.location_id,
            self.company.sedar_default_storage_location_id,
        )

    def test_tug_quarantine_requires_matching_serviceable_parent(self):
        other_parent = self.env["stock.location"].create({
            "name": "Wrong Tug Parent",
            "usage": "internal",
            "location_id": self.company.sedar_default_storage_location_id.id,
            "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env["stock.location"].create({
                "name": "Invalid Tug Quarantine",
                "usage": "internal",
                "location_id": other_parent.id,
                "company_id": self.company.id,
                "sedar_location_role": "tug_quarantine",
                "sedar_tugboat_id": self.tugboat.id,
            })

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInventoryReadinessDemand(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.tugboat = cls.env.ref("sedar_service_order_demo.tug_atlas")
        cls.product = cls.env["product.product"].create({
            "name": "Demand Test Tow Rope",
            "default_code": "TEST-DEMAND-ROPE",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.env.ref("uom.product_uom_unit").id,
            "sedar_inventory_item": True,
            "sedar_item_type": "reusable_onboard_gear",
            "sedar_readiness_critical": True,
            "sedar_compatibility_scope": "fleet",
        })
        cls.requirement = cls.env["sedar.tug.stock.requirement"].create({
            "company_id": cls.company.id,
            "product_id": cls.product.id,
            "tugboat_id": cls.tugboat.id,
            "required_qty": 2,
        })

    def _demand(self, state="open"):
        return self.env["sedar.replenishment.demand"].search([
            ("stock_requirement_id", "=", self.requirement.id),
            ("state", "=", state),
        ], limit=1)

    def test_baseline_shortage_opens_and_fulfillment_closes_episode(self):
        demand = self._demand()
        self.assertTrue(demand)
        self.assertEqual(demand.remaining_qty, 2)
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.company.sedar_default_storage_location_id, 3
        )
        movement = self.env["sedar.tug.inventory.movement"].create({
            "company_id": self.company.id,
            "action": "transfer",
            "product_id": self.product.id,
            "quantity": 3,
            "source_location_id": self.company.sedar_default_storage_location_id.id,
            "destination_location_id": self.tugboat.stock_location_id.id,
            "reason_code": "routine_replenishment",
        })
        movement.action_complete()
        self.assertEqual(demand.state, "fulfilled")
        self.assertEqual(demand.remaining_qty, 0)
        self.assertEqual(self.tugboat.inventory_readiness_status, "ready")

    def test_physical_count_separates_serviceable_and_defective(self):
        wizard = self.env["sedar.inventory.physical.count.wizard"].create({
            "company_id": self.company.id,
            "target_location_id": self.tugboat.stock_location_id.id,
            "product_id": self.product.id,
            "serviceable_count": 2,
            "defective_count": 1,
            "note": "Test count",
        })
        wizard.action_apply()
        Quant = self.env["stock.quant"]
        self.assertEqual(Quant._get_available_quantity(
            self.product, self.tugboat.stock_location_id, strict=True
        ), 2)
        self.assertEqual(Quant._get_available_quantity(
            self.product, self.tugboat.quarantine_location_id, strict=True
        ), 1)
        corrections = self.env["sedar.tug.inventory.history"].search([
            ("tugboat_id", "=", self.tugboat.id),
            ("product_id", "=", self.product.id),
            ("perspective", "=", "correction"),
        ])
        self.assertEqual(len(corrections), 2)
        self.assertEqual(self._demand("fulfilled").remaining_qty, 0)

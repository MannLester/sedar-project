from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTugInventoryMovement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.storage = cls.company.sedar_default_storage_location_id
        cls.tug_a = cls.env.ref("sedar_service_order_demo.tug_atlas")
        cls.tug_b = cls.env.ref("sedar_service_order_demo.tug_harbor_one")
        cls.product = cls.env["product.product"].create({
            "name": "Movement Test Tow Rope",
            "default_code": "TEST-MOVE-ROPE",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.env.ref("uom.product_uom_unit").id,
            "sedar_inventory_item": True,
            "sedar_item_type": "reusable_onboard_gear",
            "sedar_compatibility_scope": "fleet",
        })
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.tug_a.stock_location_id, 3
        )
        cls.user = cls.env["res.users"].create({
            "name": "Movement Test Officer",
            "login": "movement.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref(
                    "sedar_marine_inventory.group_marine_inventory_manager"
                ).id,
            ])],
        })

    def _movement(self, **values):
        defaults = {
            "company_id": self.company.id,
            "action": "transfer",
            "product_id": self.product.id,
            "quantity": 1,
            "source_location_id": self.tug_a.stock_location_id.id,
            "destination_location_id": self.tug_b.stock_location_id.id,
            "reason_code": "operational_reallocation",
        }
        defaults.update(values)
        return self.env["sedar.tug.inventory.movement"].with_user(
            self.user
        ).create(defaults)

    def test_tug_transfer_creates_one_move_and_mirrored_history(self):
        movement = self._movement()
        movement.with_user(self.user).action_complete()
        self.assertEqual(movement.state, "done")
        self.assertEqual(movement.stock_move_id.state, "done")
        self.assertEqual(len(movement.history_ids), 2)
        self.assertEqual(
            set(movement.history_ids.mapped("tugboat_id").ids),
            {self.tug_a.id, self.tug_b.id},
        )
        self.assertEqual(
            set(movement.history_ids.mapped("perspective")),
            {"outgoing", "incoming"},
        )

    def test_condition_change_uses_quarantine_and_one_history_row(self):
        movement = self._movement(
            action="mark_defective",
            destination_location_id=self.tug_a.quarantine_location_id.id,
            reason_code="defect_quarantine",
        )
        movement.with_user(self.user).action_complete()
        self.assertEqual(len(movement.history_ids), 1)
        self.assertEqual(movement.history_ids.perspective, "condition")
        self.assertEqual(movement.destination_condition, "defective")

    def test_completed_movement_and_history_are_immutable(self):
        movement = self._movement()
        movement.with_user(self.user).action_complete()
        with self.assertRaises(AccessError):
            movement.with_user(self.user).write({"note": "changed"})
        with self.assertRaises(AccessError):
            movement.history_ids.with_user(self.user).unlink()

    def test_other_reason_requires_note(self):
        with self.assertRaises(ValidationError):
            self._movement(reason_code="other")

    def test_condition_cannot_change_implicitly(self):
        movement = self._movement(
            destination_location_id=self.tug_b.quarantine_location_id.id,
        )
        with self.assertRaises(UserError):
            movement.with_user(self.user).action_complete()

    def test_completion_revalidates_source_stock(self):
        movement = self._movement(quantity=4)
        with self.assertRaises(UserError):
            movement.with_user(self.user).action_complete()

    def test_source_baseline_impact_requires_acknowledgment(self):
        self.product.sedar_readiness_critical = True
        self.env["sedar.tug.stock.requirement"].create({
            "company_id": self.company.id,
            "product_id": self.product.id,
            "tugboat_id": self.tug_a.id,
            "required_qty": 3,
        })
        movement = self._movement()
        self.assertTrue(movement.source_will_be_blocked)
        with self.assertRaises(UserError):
            movement.with_user(self.user).action_complete()
        movement.with_user(self.user).write({
            "source_shortage_acknowledged": True
        })
        movement.with_user(self.user).action_complete()
        demand = self.env["sedar.replenishment.demand"].search([
            ("tugboat_id", "=", self.tug_a.id),
            ("product_id", "=", self.product.id),
            ("state", "=", "open"),
        ])
        self.assertEqual(demand.remaining_qty, 1)

    def test_reversal_creates_a_linked_opposite_movement(self):
        movement = self._movement()
        movement.with_user(self.user).action_complete()
        reversal = movement.with_user(self.user).action_reverse()
        self.assertEqual(movement.state, "reversed")
        self.assertEqual(reversal.state, "done")
        self.assertEqual(reversal.reversal_of_id, movement)
        self.assertEqual(reversal.source_location_id, movement.destination_location_id)
        self.assertEqual(reversal.destination_location_id, movement.source_location_id)

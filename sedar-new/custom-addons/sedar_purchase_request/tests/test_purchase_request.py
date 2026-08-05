from datetime import datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSedarPurchaseRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({
            "name": "Purchase Test Supplier",
            "supplier_rank": 1,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Purchase Test Filter",
            "type": "consu",
            "is_storable": True,
        })
        cls.user = cls.env["res.users"].create({
            "name": "Purchase Test User",
            "login": "purchase.user@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_purchase_request.group_sedar_purchase_request_user").id,
            ])],
        })
        cls.manager = cls.env["res.users"].create({
            "name": "Purchase Test Manager",
            "login": "purchase.manager@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_purchase_request.group_sedar_purchase_request_manager").id,
            ])],
        })

    def _make_request(self):
        return self.env["sedar.purchase.request"].create({
            "vendor_id": self.supplier.id,
            "required_date": datetime(2026, 9, 8, 8, 0, 0),
            "source_type": "inventory",
            "justification": "Purchase request test.",
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 3,
                "estimated_unit_price": 125.0,
            })],
        })

    def test_manager_approval_creates_standard_rfq_once(self):
        request = self._make_request()
        request.action_submit()
        request.with_user(self.manager).action_approve()
        request.with_user(self.manager).action_create_rfq()

        self.assertEqual(request.state, "po_created")
        self.assertTrue(request.purchase_order_id)
        self.assertEqual(request.purchase_order_id.partner_id, self.supplier)
        self.assertEqual(request.purchase_order_id.origin, request.name)
        self.assertEqual(request.purchase_order_id.order_line.product_id, self.product)
        self.assertEqual(request.purchase_order_id.order_line.product_qty, 3)

        with self.assertRaises(UserError):
            request.with_user(self.manager).action_create_rfq()

    def test_non_manager_cannot_approve(self):
        request = self._make_request()
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.user).action_approve()

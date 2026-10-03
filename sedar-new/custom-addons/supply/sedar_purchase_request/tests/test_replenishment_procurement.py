from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReplenishmentProcurement(TransactionCase):
    def test_purchase_request_preserves_original_shortage_snapshot(self):
        company = self.env.company
        tugboat = self.env.ref("sedar_service_order_demo.tug_atlas")
        product = self.env["product.product"].create({
            "name": "Procurement Test Tow Rope",
            "default_code": "TEST-PROC-ROPE",
            "type": "consu",
            "is_storable": True,
            "uom_id": self.env.ref("uom.product_uom_unit").id,
            "sedar_inventory_item": True,
            "sedar_item_type": "reusable_onboard_gear",
            "sedar_readiness_critical": True,
            "sedar_compatibility_scope": "fleet",
        })
        requirement = self.env["sedar.tug.stock.requirement"].create({
            "company_id": company.id,
            "product_id": product.id,
            "tugboat_id": tugboat.id,
            "required_qty": 2,
        })
        demand = self.env["sedar.replenishment.demand"].search([
            ("stock_requirement_id", "=", requirement.id),
            ("state", "=", "open"),
        ], limit=1)
        action = demand.action_create_purchase_request()
        request = self.env["sedar.purchase.request"].browse(action["res_id"])
        line = request.line_ids
        self.assertEqual(line.replenishment_demand_id, demand)
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.replenishment_demand_qty, 2)
        self.env["stock.quant"]._update_available_quantity(
            product, tugboat.stock_location_id, 1
        )
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        self.assertEqual(demand.remaining_qty, 1)
        self.assertEqual(line.quantity, 2)
        with self.assertRaises(UserError):
            line.write({"quantity": 1})

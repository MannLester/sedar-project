from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSedarDemoIntegrity(TransactionCase):
    def test_two_tug_timeline_and_billable_quantity_are_consistent(self):
        order = self.env.ref("sedar_service_order_demo.order_two_tug")
        operation = self.env.ref("sedar_marine_dispatch_demo.operation_two_tug")
        assignments = order.tug_assignment_ids.filtered(lambda item: item.state != "cancelled")

        self.assertEqual(len(assignments), 2)
        self.assertEqual(max(assignments.mapped("actual_end")), datetime(2026, 8, 14, 14, 0))
        self.assertEqual(operation.actual_end, max(assignments.mapped("actual_end")))
        self.assertEqual(order.actual_billable_quantity, 12.0)
        self.assertTrue(all(
            item.returned_base_at <= operation.actual_end
            for item in operation.tug_operation_ids
        ))
        self.assertGreaterEqual(operation.client_confirmation_time, operation.actual_end)

    def test_procurement_demo_includes_stock_derived_job_order_shortage(self):
        requirement = self.env.ref("sedar_demo_suite.job_order_inventory_shortage")
        order = self.env.ref("sedar_service_order_demo.order_missing_engineer")
        assigned_tugs = order.tug_assignment_ids.filtered(
            lambda assignment: assignment.state != "cancelled"
        ).mapped("tugboat_id")

        self.assertEqual(requirement.order_id, order)
        self.assertEqual(requirement.readiness_state, "shortage")
        self.assertGreater(requirement.shortage_qty, 0)
        self.assertFalse(order.inventory_auto_ready)
        self.assertFalse(order.inventory_ready)
        self.assertTrue(assigned_tugs)
        self.assertEqual(requirement.product_id.sedar_compatibility_scope, "restricted")
        self.assertTrue(
            set(assigned_tugs.ids).issubset(
                requirement.product_id.sedar_compatible_tugboat_ids.ids
            )
        )

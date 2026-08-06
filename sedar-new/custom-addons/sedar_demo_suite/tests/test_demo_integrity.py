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

from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSedarDemoIntegrity(TransactionCase):
    def test_administrator_can_open_every_demo_workspace(self):
        admin = self.env.ref("base.user_admin")
        manager_group_xmlids = (
            "sedar_ais_demo.group_sedar_ais_manager",
            "sedar_crew_compliance.group_crew_compliance_manager",
            "sedar_executive_dashboard.group_sedar_executive",
            "sedar_hsse.group_sedar_hsse_manager",
            "sedar_manpower_planning.group_hr_manager",
            "sedar_marine_dispatch.group_dispatch_manager",
            "sedar_marine_finance.group_accounting_manager",
            "sedar_marine_inventory.group_marine_inventory_manager",
            "sedar_marine_maintenance.group_marine_maintenance_manager",
            "sedar_marine_operations.group_commercial_manager",
            "sedar_marine_operations.group_operations_manager",
            "sedar_marketing.group_marketing_manager",
            "sedar_purchase_request.group_sedar_purchase_request_manager",
            "sedar_recruitment_crewing.group_crewing_manager",
        )

        for xmlid in manager_group_xmlids:
            self.assertTrue(admin.has_group(xmlid), xmlid)

        ais_payload = self.env["sedar.ais.position"].with_user(admin).get_dashboard_data()
        self.assertTrue(ais_payload["fleet"])
        issues = self.env["sedar.inventory.issue"].with_user(admin).search([], limit=1)
        self.assertTrue(issues)
        issues.read(["name"])

        order = self.env.ref("sedar_service_order_demo.order_draft").with_user(admin)
        order.write({"special_instructions": "Administrator demo-access QA."})

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

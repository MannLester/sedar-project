from odoo.tests.common import TransactionCase


class TestSedarExecutiveDashboard(TransactionCase):
    def test_corporate_register_has_controlled_sources(self):
        records = self.env["sedar.corporate.record"].search([])
        self.assertEqual(len(records), 7)
        self.assertTrue(all(record.document_id for record in records))
        self.assertTrue(self.env["sedar.document"].search_count([("document_category", "in", ["corporate", "vessel"])]))

    def test_dashboard_reads_source_facts_and_drilldowns(self):
        dashboard = self.env.ref("sedar_executive_dashboard.executive_dashboard_demo")
        self.assertGreaterEqual(dashboard.service_order_count, 1)
        self.assertGreaterEqual(dashboard.revenue_total, 0)
        self.assertGreaterEqual(dashboard.governance_exception_count, 1)
        action = dashboard.action_open_service_orders()
        self.assertEqual(action["res_model"], "sedar.marine.service.order")
        self.assertEqual(action["type"], "ir.actions.act_window")


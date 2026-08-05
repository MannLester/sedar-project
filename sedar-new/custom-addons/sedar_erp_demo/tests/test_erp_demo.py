from odoo.tests.common import TransactionCase


class TestSedarErpDemo(TransactionCase):
    def test_hr_finance_and_crm_demo_sources_exist(self):
        self.assertTrue(self.env["hr.attendance"].search_count([]))
        self.assertTrue(self.env["sedar.hr.performance.review"].search_count([]))
        self.assertTrue(self.env["sedar.hr.payroll.input"].search_count([]))
        budget = self.env.ref("sedar_erp_demo.budget_demo_operations")
        self.assertEqual(budget.variance, budget.planned_amount - budget.actual_amount)
        asset = self.env.ref("sedar_erp_demo.asset_demo_tugboat")
        self.assertGreater(asset.monthly_depreciation, 0)
        opportunity = self.env["crm.lead"].search([("sedar_demo_only", "=", True)], limit=1)
        self.assertTrue(opportunity)
        self.assertTrue(opportunity.sedar_service_order_id)
        self.assertTrue(opportunity.activity_ids)

    def test_demo_accounting_records_are_posted(self):
        moves = self.env["account.move"].search([("ref", "in", ["SEDAR-ERP-DEMO-SALE", "SEDAR-ERP-DEMO-BILL"])])
        self.assertEqual(len(moves), 2)
        self.assertTrue(all(move.state == "posted" for move in moves))


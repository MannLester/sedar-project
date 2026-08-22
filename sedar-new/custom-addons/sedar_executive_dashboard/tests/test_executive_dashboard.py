from odoo import fields
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

    def test_service_order_kpis_and_drilldown_use_dashboard_company(self):
        main_dashboard = self.env.ref("sedar_executive_dashboard.executive_dashboard_demo")
        main_count = main_dashboard.service_order_count
        other_company = self.env["res.company"].create({"name": "Other Dashboard Company"})
        service = self.env["sedar.marine.service.type"].create({
            "name": "Dashboard Company Service",
            "code": "DASH-COMPANY",
            "pricing_basis": "per_service",
        })
        port = self.env["sedar.marine.port"].create({
            "name": "Dashboard Company Port",
            "code": "DASH-COMPANY",
        })
        order = self.env["sedar.marine.service.order"].with_company(other_company).create({
            "company_id": other_company.id,
            "client_id": self.env["res.partner"].create({"name": "Dashboard Client"}).id,
            "assisted_vessel_name": "MV Dashboard Company",
            "service_type_id": service.id,
            "scope_of_work": "Verify company-scoped executive facts.",
            "port_id": port.id,
            "requested_start": fields.Datetime.now(),
        })
        other_dashboard = self.env["sedar.executive.dashboard"].create({
            "name": "Other Company Dashboard",
            "company_id": other_company.id,
        })

        self.assertEqual(main_dashboard.service_order_count, main_count)
        self.assertEqual(other_dashboard.service_order_count, 1)
        self.assertEqual(
            other_dashboard.action_open_service_orders()["domain"],
            [("company_id", "=", other_company.id)],
        )
        self.assertEqual(
            other_dashboard.action_open_invoices()["domain"],
            [
                ("company_id", "=", other_company.id),
                ("state", "=", "posted"),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ],
        )
        self.assertEqual(order.company_id, other_company)

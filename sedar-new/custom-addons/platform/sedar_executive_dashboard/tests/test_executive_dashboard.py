from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tests.common import new_test_user
from odoo.tools import file_open


class TestSedarExecutiveDashboard(TransactionCase):
    def test_dashboard_perspective_is_saved_per_user(self):
        executive = new_test_user(
            self.env,
            login="dashboard_perspective_user",
            groups="sedar_executive_dashboard.group_sedar_executive",
        )
        dashboard = self.env.ref(
            "sedar_executive_dashboard.executive_dashboard_demo"
        ).with_user(executive)

        action = dashboard.with_context(
            dashboard_perspective="operations"
        ).action_set_dashboard_perspective()

        self.assertEqual(executive.sedar_executive_dashboard_view, "operations")
        self.assertEqual(action["res_id"], dashboard.id)
        self.assertEqual(action["res_model"], "sedar.executive.dashboard")
        with self.assertRaises(UserError):
            dashboard.with_context(
                dashboard_perspective="unsupported"
            ).action_set_dashboard_perspective()

    def test_dashboard_perspectives_focus_attention_counts(self):
        dashboard = self.env.ref("sedar_executive_dashboard.executive_dashboard_demo")

        self.assertEqual(
            dashboard._perspective_attention_count("finance"),
            dashboard.overdue_receivable_count + dashboard.billing_review_count,
        )
        self.assertEqual(
            dashboard._perspective_attention_count("people"),
            dashboard.credential_expiry_count
            + dashboard.open_shortage_count
            + dashboard.hsse_overdue_action_count,
        )
        self.assertEqual(
            dashboard._perspective_attention_count("owner"),
            dashboard.attention_total_count,
        )

    def test_dashboard_view_exposes_four_role_presets(self):
        with file_open(
            "sedar_executive_dashboard/views/sedar_executive_views.xml"
        ) as view_file:
            view = view_file.read()

        self.assertIn("Owner Overview", view)
        self.assertIn(">Operations</", view)
        self.assertIn(">Finance</", view)
        self.assertIn("Crewing &amp; Safety", view)
        self.assertIn("VISUAL COMPANY PULSE", view)
        self.assertIn('name="visualization_html"', view)

    def test_dashboard_visualizations_explain_each_perspective(self):
        dashboard = self.env.ref("sedar_executive_dashboard.executive_dashboard_demo")
        expected_titles = {
            "owner": ["Revenue and known costs", "Fleet readiness", "Service delivery", "Risk concentration"],
            "operations": ["Fleet readiness", "Service workflow", "Readiness blockers", "Support workload"],
            "finance": ["Revenue and known costs", "Cash conversion", "Billing pipeline", "Financial pressure"],
            "people": ["Crew availability", "Staffing pipeline", "Compliance exposure", "Safety workload"],
        }

        for perspective, titles in expected_titles.items():
            dashboard.env.user.sedar_executive_dashboard_view = perspective
            dashboard.invalidate_recordset(["dashboard_perspective", "visualization_html"])
            visual = str(dashboard.visualization_html)
            self.assertEqual(visual.count('class="sedar_chart_card'), 4)
            for title in titles:
                self.assertIn(title, visual)

        dashboard.env.user.sedar_executive_dashboard_view = "owner"
        dashboard.invalidate_recordset(["dashboard_perspective", "visualization_html"])
        self.assertEqual(
            str(dashboard.visualization_html).count('class="sedar_trend_row"'),
            6,
        )

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
        self.assertEqual(dashboard.reporting_date, fields.Date.context_today(dashboard))
        self.assertIn("cost-allocation", dashboard.profitability_note)
        self.assertIn("intentionally not reported", dashboard.utilization_note)
        action = dashboard.action_open_service_orders()
        self.assertEqual(action["res_model"], "sedar.marine.service.order")
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_attention_queue_uses_source_record_domains(self):
        dashboard = self.env.ref("sedar_executive_dashboard.executive_dashboard_demo")
        expected = sum([
            dashboard.overdue_receivable_count,
            dashboard.billing_review_count,
            dashboard.blocked_service_order_count,
            dashboard.credential_expiry_count,
            dashboard.maintenance_blocker_count,
            dashboard.inventory_shortage_count,
            dashboard.purchase_overdue_count,
            dashboard.hsse_overdue_action_count,
            dashboard.document_expiry_count,
        ])
        self.assertEqual(dashboard.attention_total_count, expected)
        self.assertEqual(
            dashboard.action_open_overdue_receivables()["res_model"],
            "account.move",
        )
        self.assertEqual(
            dashboard.action_open_blocked_service_orders()["res_model"],
            "sedar.marine.service.order",
        )
        self.assertEqual(
            dashboard.action_open_overdue_hsse_actions()["res_model"],
            "sedar.hsse.corrective.action",
        )

    def test_flagship_walkthrough_opens_a_service_order(self):
        dashboard = self.env.ref("sedar_executive_dashboard.executive_dashboard_demo")
        action = dashboard.action_open_flagship_service()
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

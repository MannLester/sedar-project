import json
from datetime import datetime
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sedar_demo_suite.hooks import (
    DEMO_MANAGER_GROUP_XMLIDS,
    _bind_xmlid,
    _ensure_inventory_breadth,
    _ensure_pm_procurement_demo,
    _immutable_record,
    _record,
)


@tagged("post_install", "-at_install")
class TestSedarDemoIntegrity(TransactionCase):
    def _pm_snapshot(self):
        request = self.env.ref("sedar_demo_suite.pm_request").sudo()
        bids = request.bid_ids.sorted("id")
        orders = request.purchase_order_ids.sorted("id")
        issue = self.env.ref("sedar_demo_suite.pm_inventory_issue_a")
        xmlids = [
            "pm_request",
            "pm_request_line_a", "pm_request_line_b", "pm_request_line_c",
            "pm_bid_1", "pm_bid_2", "pm_bid_3",
            "pm_bid_line_one_a", "pm_bid_line_one_b", "pm_bid_line_two_a",
            "pm_bid_line_three_b", "pm_bid_line_three_c",
            "pm_award_a", "pm_award_b", "pm_award_c",
            "pm_purchase_order_bidder_one", "pm_purchase_order_bidder_three",
            "pm_purchase_order_line_a", "pm_purchase_order_line_b",
            "pm_purchase_order_line_c",
            "pm_bid_one_quotation", "pm_bid_two_quotation",
            "pm_bid_three_quotation",
            "pm_receipt_bidder_one", "pm_receipt_bidder_three",
            "pm_inventory_issue_a", "pm_inventory_issue_move_a",
            "pm_inventory_lifecycle_a", "pm_running_hour_baseline",
            "pm_running_hour_current", "pm_due_maintenance_activity",
            "pm_product_c_serial",
        ]
        return {
            "xmlids": {
                xmlid: self.env.ref(f"sedar_demo_suite.{xmlid}").id
                for xmlid in xmlids
            },
            "bid_lines": tuple(bids.line_ids.sorted("id").ids),
            "bid_content": tuple(
                (bid.id, bid.state, bid.total_amount, tuple(bid.line_ids.ids))
                for bid in bids
            ),
            "awards": tuple(
                (award.id, award.state, award.purchase_order_line_id.id)
                for award in request.award_ids.sorted("id")
            ),
            "orders": tuple(
                (
                    order.id,
                    order.state,
                    tuple(order.order_line.sorted("id").ids),
                    tuple(order.picking_ids.sorted("id").ids),
                )
                for order in orders
            ),
            "issue": (
                issue.id,
                issue.stock_move_id.id,
                issue.lifecycle_id.id,
                tuple(issue.lifecycle_id.event_ids.ids),
            ),
        }

    def test_administrator_can_open_every_demo_workspace(self):
        admin = self.env.ref("base.user_admin")

        for xmlid in DEMO_MANAGER_GROUP_XMLIDS:
            self.assertTrue(admin.has_group(xmlid), xmlid)

        ais_payload = self.env["sedar.ais.position"].with_user(admin).get_dashboard_data()
        self.assertTrue(ais_payload["fleet"])
        issues = self.env["sedar.inventory.issue"].with_user(admin).search([], limit=1)
        self.assertTrue(issues)
        issues.read(["name"])

        order = self.env.ref("sedar_service_order_demo.order_draft").with_user(admin)
        order.write({"special_instructions": "Administrator demo-access QA."})

    def test_internal_demo_personas_receive_demo_access_override(self):
        personas = self.env["res.users"].search([
            ("active", "=", True),
            ("share", "=", False),
            ("login", "=like", "%@sedar.demo"),
        ])
        self.assertTrue(personas)

        for persona in personas:
            for xmlid in DEMO_MANAGER_GROUP_XMLIDS:
                self.assertTrue(
                    persona.has_group(xmlid),
                    f"{persona.login} is missing {xmlid}",
                )

        procurement = self.env.ref("sedar_purchase_request.user_procurement_manager")
        ais_payload = self.env["sedar.ais.position"].with_user(
            procurement
        ).get_dashboard_data()
        self.assertTrue(ais_payload["fleet"])
        self.env["sedar.inventory.issue"].with_user(procurement).search(
            [], limit=1
        ).read(["name"])
        self.env["sedar.marine.service.order"].with_user(procurement).search(
            [], limit=1
        ).read(["name"])

    def test_portal_demo_personas_remain_restricted(self):
        portal_users = (
            self.env.ref("sedar_service_order_demo.user_client_portal"),
            self.env.ref("sedar_recruitment_demo.user_applicant_portal"),
        )
        for portal_user in portal_users:
            self.assertTrue(portal_user.share)
            for xmlid in DEMO_MANAGER_GROUP_XMLIDS:
                self.assertFalse(
                    portal_user.has_group(xmlid),
                    f"{portal_user.login} unexpectedly received {xmlid}",
                )

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
        officer = self.env.ref("sedar_purchase_request.user_procurement_manager")
        self.assertEqual(
            self.env.company.sedar_procurement_inventory_officer_id,
            officer,
        )

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

    def test_pm_procurement_scenario_matches_the_approved_line_awards(self):
        request = self.env.ref("sedar_demo_suite.pm_request").sudo()
        products = {
            key: self.env.ref(f"sedar_demo_suite.pm_product_{xmlid}")
            for key, xmlid in {
                "a": "a_filter",
                "b": "b_lube",
                "c": "c_replacement_pump",
            }.items()
        }
        bidders = {
            key: self.env.ref(f"sedar_demo_suite.pm_bidder_{index}")
            for key, index in {"one": 1, "two": 2, "three": 3}.items()
        }
        bids = {
            key: self.env.ref(f"sedar_demo_suite.pm_bid_{index}")
            for key, index in {"one": 1, "two": 2, "three": 3}.items()
        }

        self.assertEqual(request.equipment_id, self.env.ref(
            "sedar_marine_maintenance.atlas_main_engine"
        ))
        self.assertEqual(len(request.line_ids), 3)
        self.assertEqual(len(request.bid_ids), 3)
        self.assertEqual(len(request.bid_ids.line_ids), 5)
        self.assertEqual(len(request.award_ids), 3)
        self.assertEqual(len(request.purchase_order_ids), 2)
        self.assertEqual(
            set(bids["one"].line_ids.product_id.ids),
            {products["a"].id, products["b"].id},
        )
        self.assertEqual(
            set(bids["two"].line_ids.product_id.ids), {products["a"].id}
        )
        self.assertEqual(
            set(bids["three"].line_ids.product_id.ids),
            {products["b"].id, products["c"].id},
        )
        order_one = request.purchase_order_ids.filtered(
            lambda order: order.sedar_bid_id == bids["one"]
        )
        order_three = request.purchase_order_ids.filtered(
            lambda order: order.sedar_bid_id == bids["three"]
        )
        self.assertEqual(order_one.partner_id, bidders["one"])
        self.assertEqual(order_three.partner_id, bidders["three"])
        self.assertEqual(
            set(order_one.order_line.product_id.ids),
            {products["a"].id, products["b"].id},
        )
        self.assertEqual(
            set(order_three.order_line.product_id.ids), {products["c"].id}
        )

    def test_pm_receipts_feed_storage_and_issue_current_use(self):
        storage = self.env.company.sedar_default_storage_location_id
        product_a = self.env.ref("sedar_demo_suite.pm_product_a_filter")
        product_b = self.env.ref("sedar_demo_suite.pm_product_b_lube")
        product_c = self.env.ref(
            "sedar_demo_suite.pm_product_c_replacement_pump"
        )
        issue = self.env.ref("sedar_demo_suite.pm_inventory_issue_a")
        lifecycle = self.env.ref("sedar_demo_suite.pm_inventory_lifecycle_a")
        serial = self.env.ref("sedar_demo_suite.pm_product_c_serial")
        available = self.env["stock.quant"]._get_available_quantity

        self.assertEqual(available(product_a, storage, strict=True), 3.0)
        self.assertEqual(available(product_b, storage, strict=True), 60.0)
        self.assertEqual(
            available(product_c, storage, lot_id=serial, strict=True), 1.0
        )
        self.assertEqual(issue.stock_move_id.state, "done")
        self.assertEqual(issue.stock_move_id.location_dest_id, issue.tug_location_id)
        self.assertEqual(lifecycle.state, "open")
        self.assertEqual(lifecycle.usage_state, "onboard")
        self.assertEqual(lifecycle.open_qty, 1.0)
        self.assertEqual(
            available(product_a, issue.tug_location_id, strict=True), 1.0
        )

    def test_pm_map_projection_and_restricted_redaction(self):
        equipment = self.env.ref("sedar_marine_maintenance.atlas_main_engine")
        officer = self.env.company.sedar_procurement_inventory_officer_id
        detail = self.env["sedar.ais.position"].with_user(
            officer
        ).get_equipment_procurement_detail(equipment.id)
        self.assertEqual(detail["access"], "full")
        self.assertFalse(detail["active_procurement"])
        self.assertEqual(len(detail["procurement_history"]), 3)
        bidder_names = {
            bid["bidder_name"]
            for row in detail["procurement_history"]
            for bid in row["commercial"]["bids"]
        }
        self.assertEqual(bidder_names, {
            self.env.ref("sedar_demo_suite.pm_bidder_1").name,
            self.env.ref("sedar_demo_suite.pm_bidder_2").name,
            self.env.ref("sedar_demo_suite.pm_bidder_3").name,
        })

        restricted = self.env["res.users"].create({
            "name": "PM Map Restricted User",
            "login": "pm.map.restricted@test.example",
            "company_id": self.env.company.id,
            "company_ids": [Command.set([self.env.company.id])],
            "group_ids": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("sedar_ais_demo.group_sedar_ais_user").id,
            ])],
        })
        limited = self.env["sedar.ais.position"].with_user(
            restricted
        ).get_equipment_procurement_detail(equipment.id)
        self.assertEqual(limited["access"], "limited")
        serialized = json.dumps(limited).lower()
        for protected in (
            "bidder 1", "bidder 2", "bidder 3", "unit_price",
            "warranty", "quotation", "commercial", "supplier_name",
        ):
            self.assertNotIn(protected, serialized)

    def test_pm_reconciliation_is_semantically_idempotent(self):
        before = self._pm_snapshot()
        _ensure_pm_procurement_demo(self.env)
        _ensure_pm_procurement_demo(self.env)
        self.assertEqual(self._pm_snapshot(), before)

    def test_inventory_breadth_does_not_reset_operational_quantities(self):
        product = self.env.ref("sedar_demo_suite.inventory_item_battery")
        storage = self.env.company.sedar_default_storage_location_id
        self.env["stock.quant"]._update_available_quantity(product, storage, -1.0)
        before = self.env["stock.quant"]._get_available_quantity(
            product, storage, strict=True
        )
        _ensure_inventory_breadth(self.env)
        after = self.env["stock.quant"]._get_available_quantity(
            product, storage, strict=True
        )
        self.assertEqual(after, before)

    def test_company_reconciliation_uses_each_selected_company_context(self):
        other_company = self.env["res.company"].create({
            "name": "Demo Suite Context Company",
        })
        seen_company_ids = []

        def capture_company(environment):
            seen_company_ids.append(environment.company.id)

        with patch(
            "odoo.addons.sedar_demo_suite.hooks.post_init_hook",
            side_effect=capture_company,
        ):
            (self.env.company | other_company).sedar_reconcile_demo_suite()

        self.assertEqual(
            seen_company_ids, [self.env.company.id, other_company.id]
        )

    def test_generic_record_rejects_wrong_model_xmlid_without_rewrite(self):
        partner = self.env["res.partner"].create({"name": "Unrelated Partner"})
        self.env["ir.model.data"].create({
            "module": "sedar_demo_suite",
            "name": "corrupt_generic_wrong_model",
            "model": partner._name,
            "res_id": partner.id,
            "noupdate": True,
        })

        with self.assertRaisesRegex(UserError, "points to res.partner"):
            _record(
                self.env,
                "product.product",
                "corrupt_generic_wrong_model",
                {"name": "Must Not Replace Partner"},
            )

        self.assertEqual(partner.name, "Unrelated Partner")
        self.assertFalse(self.env["product.product"].search([
            ("name", "=", "Must Not Replace Partner"),
        ]))

    def test_immutable_record_rejects_mismatched_business_identity(self):
        unrelated = self.env["product.product"].create({
            "name": "Unrelated Same-model Product",
            "company_id": self.env.company.id,
            "default_code": "UNRELATED-CODE",
        })
        self.env["ir.model.data"].create({
            "module": "sedar_demo_suite",
            "name": "corrupt_pm_product",
            "model": unrelated._name,
            "res_id": unrelated.id,
            "noupdate": True,
        })
        expected = {
            "name": "Expected PM Product",
            "company_id": self.env.company.id,
            "default_code": "EXPECTED-PM-CODE",
        }

        with self.assertRaisesRegex(UserError, "mismatched business identity"):
            _immutable_record(
                self.env,
                "product.product",
                "corrupt_pm_product",
                expected,
                identity_fields=("company_id", "default_code"),
            )

        self.assertEqual(unrelated.default_code, "UNRELATED-CODE")
        self.assertEqual(unrelated.name, "Unrelated Same-model Product")

    def test_immutable_record_and_binding_reject_cross_company_or_rebind(self):
        other_company = self.env["res.company"].create({
            "name": "Fixture Identity Other Company",
        })
        foreign = self.env["product.product"].create({
            "name": "Foreign Fixture Product",
            "company_id": other_company.id,
            "default_code": "FOREIGN-FIXTURE",
        })
        self.env["ir.model.data"].create({
            "module": "sedar_demo_suite",
            "name": "corrupt_cross_company_product",
            "model": foreign._name,
            "res_id": foreign.id,
            "noupdate": True,
        })
        expected = {
            "name": "Expected Local Fixture Product",
            "company_id": self.env.company.id,
            "default_code": "LOCAL-FIXTURE",
        }
        with self.assertRaisesRegex(UserError, "belongs to another company"):
            _immutable_record(
                self.env,
                "product.product",
                "corrupt_cross_company_product",
                expected,
                identity_fields=("company_id", "default_code"),
            )

        local = self.env["product.product"].create({
            "name": "Local Replacement Candidate",
            "company_id": self.env.company.id,
            "default_code": "LOCAL-REPLACEMENT",
        })
        with self.assertRaisesRegex(UserError, "without rebinding"):
            _bind_xmlid(self.env, "corrupt_cross_company_product", local)
        self.assertEqual(
            self.env.ref("sedar_demo_suite.corrupt_cross_company_product"),
            foreign,
        )

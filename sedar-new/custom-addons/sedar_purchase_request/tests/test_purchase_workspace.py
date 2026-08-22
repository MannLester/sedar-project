import base64
import importlib.util
from datetime import datetime
from pathlib import Path

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


OFFICER_GROUP = "sedar_marine_inventory.group_marine_inventory_manager"


@tagged("post_install", "-at_install")
class TestProcurementWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.officer_group = cls.env.ref(OFFICER_GROUP)
        cls.maintenance_manager_group = cls.env.ref(
            "sedar_marine_maintenance.group_marine_maintenance_manager"
        )
        cls.request_group = cls.env.ref(
            "sedar_purchase_request.group_sedar_purchase_request_user"
        )
        cls.requester = cls.env["res.users"].create({
            "name": "Workspace Requester",
            "login": "workspace.requester@test.example",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set([cls.env.company.id])],
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id, cls.request_group.id,
            ])],
        })

    def test_actions_use_exact_workspace_scope_and_groups(self):
        bids = self.env.ref("sedar_purchase_request.action_sedar_purchase_bids")
        comparison = self.env.ref(
            "sedar_purchase_request.action_sedar_purchase_bid_comparison"
        )
        orders = self.env.ref(
            "sedar_purchase_request.action_sedar_generated_purchase_orders"
        )

        self.assertEqual(bids.name, "Bidder List")
        self.assertIn(self.officer_group, bids.group_ids)
        self.assertEqual(
            safe_eval(comparison.domain), [("bid_id.state", "=", "received")]
        )
        self.assertEqual(
            safe_eval(comparison.context),
            {
                "search_default_group_request": 1,
                "search_default_group_request_line": 2,
            },
        )
        self.assertIn(self.officer_group, comparison.group_ids)
        self.assertEqual(
            safe_eval(orders.domain),
            [("sedar_purchase_request_id", "!=", False)],
        )
        self.assertNotIn(("state", "!=", "draft"), safe_eval(orders.domain))
        self.assertIn(self.officer_group, orders.group_ids)

        generated_order_list = self.env.ref(
            "sedar_purchase_request.view_sedar_generated_purchase_order_list"
        )
        self.assertIn(
            generated_order_list,
            orders.view_ids.mapped("view_id"),
        )
        order_list_arch = etree.fromstring(generated_order_list.arch_db)
        self.assertEqual(order_list_arch.get("sample"), "0")
        self.assertEqual(order_list_arch.get("create"), "0")
        self.assertTrue(order_list_arch.xpath("./field[@name='sedar_purchase_request_id']"))

    def test_workspace_views_prioritize_required_desktop_and_mobile_controls(self):
        request_list = etree.fromstring(self.env.ref(
            "sedar_purchase_request.view_sedar_purchase_request_list"
        ).arch_db)
        fields = request_list.xpath("./field")
        field_names = [field.get("name") for field in fields]
        self.assertLess(field_names.index("state"), field_names.index("required_date"))
        self.assertLess(
            field_names.index("procurement_progress"),
            field_names.index("required_date"),
        )
        self.assertEqual(
            request_list.xpath("./field[@name='equipment_id']")[0].get("optional"),
            "hide",
        )

        request_form = etree.fromstring(self.env.ref(
            "sedar_purchase_request.view_sedar_purchase_request_form"
        ).arch_db)
        mobile_actions = request_form.xpath(
            ".//div[contains(concat(' ', normalize-space(@class), ' '), "
            "' o_sedar_mobile_procurement_actions ')]"
        )
        self.assertEqual(len(mobile_actions), 1)
        self.assertIn("d-md-none", mobile_actions[0].get("class").split())
        self.assertEqual(
            {button.get("name") for button in mobile_actions[0].xpath("./button")},
            {
                "action_open_bids",
                "action_open_bid_comparison",
                "action_open_purchase_orders",
            },
        )

        comparison = etree.fromstring(self.env.ref(
            "sedar_purchase_request.view_sedar_purchase_bid_line_comparison_list"
        ).arch_db)
        self.assertEqual(
            comparison.xpath("./field[@name='bidder_id']")[0].get("width"),
            "240px",
        )
        self.assertEqual(
            comparison.xpath("./field[@name='quantity']")[0].get("optional"),
            "hide",
        )
        self.assertEqual(
            comparison.xpath("./field[@name='promised_delivery_date']")[0].get(
                "optional"
            ),
            "hide",
        )

    def test_bidder_list_defines_non_overlapping_operational_filters(self):
        arch = self.env.ref(
            "sedar_purchase_request.view_sedar_purchase_bid_search"
        ).arch_db
        for filter_name in (
            "active_bids", "partial_coverage", "has_awards", "no_awards",
            "closed_expired_history",
        ):
            self.assertIn(f'name="{filter_name}"', arch)
        self.assertIn("context_today()", arch)
        self.assertIn("coverage_state", arch)
        self.assertIn("award_count", arch)

    def test_procurement_menu_tree_converges_on_native_actions(self):
        root = self.env.ref("sedar_purchase_request.menu_sedar_procurement_root")
        inventory = self.env.ref(
            "sedar_purchase_request.menu_sedar_procurement_inventory"
        )
        storage = self.env.ref(
            "sedar_purchase_request.menu_sedar_procurement_storage"
        )
        in_use = self.env.ref(
            "sedar_purchase_request.menu_sedar_procurement_currently_in_use"
        )

        self.assertEqual(inventory.parent_id, root)
        self.assertEqual(storage.parent_id, inventory)
        self.assertEqual(in_use.parent_id, inventory)
        self.assertEqual(
            storage.action, self.env.ref("sedar_marine_inventory.action_inventory_check")
        )
        self.assertEqual(
            in_use.action,
            self.env.ref("sedar_marine_inventory.action_inventory_currently_in_use"),
        )
        self.assertIn(self.officer_group, inventory.group_ids)
        self.assertIn(self.maintenance_manager_group, inventory.group_ids)
        self.assertIn(self.officer_group, storage.group_ids)
        self.assertNotIn(self.maintenance_manager_group, storage.group_ids)
        self.assertIn(self.officer_group, in_use.group_ids)
        self.assertIn(self.maintenance_manager_group, in_use.group_ids)
        self._assert_legacy_inventory_menus_inactive()

    def test_upgrade_migration_deactivates_reactivated_legacy_menus(self):
        legacy_root = self.env.ref(
            "sedar_marine_inventory.menu_marine_inventory_root"
        )
        legacy_root.active = True
        migration_path = (
            Path(get_module_path("sedar_purchase_request"))
            / "migrations/19.0.6.0.0/post-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_purchase_workspace_post_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        migration.migrate(self.env.cr, "19.0.5.0.0")
        legacy_root.invalidate_recordset(["active"])
        self._assert_legacy_inventory_menus_inactive()

    def _assert_legacy_inventory_menus_inactive(self):
        for xmlid in (
            "menu_marine_inventory_root", "menu_inventory_check",
            "menu_inventory_currently_in_use", "menu_inventory_issues",
            "menu_inventory_requirements", "menu_inventory_templates",
        ):
            menu = self.env.ref(f"sedar_marine_inventory.{xmlid}")
            menu.invalidate_recordset(["active"])
            self.assertFalse(menu.active)

    def test_requester_has_no_direct_purchase_or_commercial_action_access(self):
        self.assertFalse(self.requester.has_group("purchase.group_purchase_user"))
        with self.assertRaises(AccessError):
            self.env["purchase.order"].with_user(self.requester).search_read(
                [], ["name", "amount_total"]
            )
        for action_xmlid in (
            "action_sedar_purchase_bids",
            "action_sedar_purchase_bid_comparison",
            "action_sedar_generated_purchase_orders",
        ):
            action = self.env.ref(f"sedar_purchase_request.{action_xmlid}")
            with self.assertRaises(AccessError):
                action.with_user(self.requester).read(["name", "domain"])


@tagged("post_install", "-at_install")
class TestBidQuotationDownloadSecurity(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base_group = cls.env.ref("base.group_user")
        request_group = cls.env.ref(
            "sedar_purchase_request.group_sedar_purchase_request_user"
        )
        officer_group = cls.env.ref(OFFICER_GROUP)
        cls.requester = cls.env["res.users"].create({
            "name": "Download Requester",
            "login": "download.requester@test.example",
            "password": "requester-password",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set([cls.env.company.id])],
            "group_ids": [Command.set([base_group.id, request_group.id])],
        })
        cls.officer = cls.env["res.users"].create({
            "name": "Download Procurement Officer",
            "login": "download.officer@test.example",
            "password": "officer-password",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set([cls.env.company.id])],
            "group_ids": [Command.set([
                base_group.id, request_group.id, officer_group.id,
            ])],
        })
        cls.env.company.sudo().sedar_procurement_inventory_officer_id = cls.officer
        supplier = cls.env["res.partner"].create({
            "name": "Download Bidder", "supplier_rank": 1,
        })
        product = cls.env["product.product"].create({
            "name": "Download Test Product", "type": "consu", "is_storable": True,
        })
        request = cls.env["sedar.purchase.request"].with_user(cls.requester).create({
            "required_date": datetime(2026, 9, 8, 8, 0, 0),
            "source_type": "manual",
            "justification": "Verify quotation download security.",
            "line_ids": [Command.create({
                "product_id": product.id, "quantity": 1,
            })],
        })
        request.with_user(cls.requester).action_submit()
        request.with_user(cls.officer).action_approve()
        cls.secret = b"private-download-quotation"
        bid = cls.env["sedar.purchase.bid"].with_user(cls.officer).create({
            "request_id": request.id,
            "bidder_id": supplier.id,
            "quotation_filename": "private.txt",
            "quotation_file": base64.b64encode(cls.secret),
            "line_ids": [Command.create({
                "request_line_id": request.line_ids.id, "unit_price": 10.0,
            })],
        })
        cls.attachment = cls.env["ir.attachment"].sudo().search([
            ("res_model", "=", "sedar.purchase.bid"),
            ("res_id", "=", bid.id),
            ("res_field", "=", "quotation_file"),
        ], limit=1)

    def test_requester_cannot_download_bid_quotation_by_attachment_id(self):
        self.authenticate(self.requester.login, "requester-password")
        response = self.url_open(
            f"/web/content/{self.attachment.id}?download=true"
        )
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(self.secret, response.content)

        self.authenticate(self.officer.login, "officer-password")
        response = self.url_open(
            f"/web/content/{self.attachment.id}?download=true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.secret)

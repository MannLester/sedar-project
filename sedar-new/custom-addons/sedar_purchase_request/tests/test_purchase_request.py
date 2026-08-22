from datetime import date, datetime
import importlib.util
from pathlib import Path

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools import convert_file


@tagged("post_install", "-at_install")
class TestSedarPurchaseRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create({
            "name": "Purchase Test Supplier", "supplier_rank": 1,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Purchase Test Filter", "type": "consu", "is_storable": True,
        })
        cls.service = cls.env["product.product"].create({
            "name": "External Repair Service", "type": "service",
        })
        combo_choice = cls.env["product.combo"].create({
            "name": "Non-stock Combo Choice",
            "combo_item_ids": [Command.create({"product_id": cls.product.id})],
        })
        cls.combo = cls.env["product.product"].create({
            "name": "Non-stock Combo",
            "type": "combo",
            "combo_ids": [Command.link(combo_choice.id)],
        })
        user_group = cls.env.ref("sedar_purchase_request.group_sedar_purchase_request_user")
        officer_group = cls.env.ref("sedar_marine_inventory.group_marine_inventory_manager")
        cls.user = cls.env["res.users"].create({
            "name": "Purchase Test User", "login": "purchase.user@test.example",
            "company_id": cls.company.id, "company_ids": [(6, 0, [cls.company.id])],
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, user_group.id])],
        })
        cls.officer = cls.env["res.users"].create({
            "name": "Procurement and Inventory Officer", "login": "procurement.officer@test.example",
            "company_id": cls.company.id, "company_ids": [(6, 0, [cls.company.id])],
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, user_group.id, officer_group.id])],
        })
        cls.other_officer = cls.env["res.users"].create({
            "name": "Other Inventory Officer", "login": "other.officer@test.example",
            "company_id": cls.company.id, "company_ids": [(6, 0, [cls.company.id])],
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, user_group.id, officer_group.id])],
        })
        cls.company.sudo().sedar_procurement_inventory_officer_id = cls.officer

    def _make_request(self, **values):
        vals = {
            "required_date": datetime(2026, 9, 8, 8, 0, 0),
            "source_type": "inventory",
            "justification": "Purchase request test.",
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 3,
                "estimated_unit_price": 125.0,
            })],
        }
        vals.update(values)
        return self.env["sedar.purchase.request"].with_user(self.user).create(vals)

    def test_vendorless_submit_creates_one_officer_review_activity(self):
        request = self._make_request()

        request.with_user(self.user).action_submit()
        request._reconcile_review_activity()

        activities = request._open_review_activities()
        self.assertEqual(request.state, "submitted")
        self.assertFalse(request.vendor_id)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.officer)
        self.assertEqual(activities.activity_type_id, self.env.ref(
            "sedar_purchase_request.mail_activity_type_purchase_request_review"
        ))

    def test_only_exact_configured_officer_can_approve_or_reject(self):
        request = self._make_request()
        self.assertTrue(request.with_user(self.officer).is_procurement_inventory_officer)
        self.assertFalse(request.with_user(self.other_officer).is_procurement_inventory_officer)
        request.with_user(self.user).action_submit()

        with self.assertRaises(AccessError):
            request.with_user(self.other_officer).action_approve()
        request.with_user(self.officer).action_approve()

        self.assertEqual(request.state, "approved")
        self.assertEqual(request.approved_by_id, self.officer)
        self.assertFalse(request._open_review_activities())

        request.with_user(self.officer).write({"rejection_reason": "Need specification correction."})
        request.with_user(self.officer).action_reject()
        self.assertEqual(request.state, "rejected")
        self.assertEqual(request.rejected_by_id, self.officer)
        self.assertTrue(any(
            "Need specification correction." in str(message.body)
            for message in request.message_ids
        ))
        with self.assertRaises(AccessError):
            request.with_user(self.user).write({"rejection_reason": "Rewritten by requester."})

        request.with_user(self.user).write({"justification": "Corrected specification."})
        request.with_user(self.user).action_submit()
        self.assertFalse(request.rejection_reason)
        self.assertFalse(request.rejected_by_id)
        self.assertFalse(request.rejected_at)
        self.assertTrue(any(
            "Need specification correction." in str(message.body)
            for message in request.message_ids
        ))

    def test_open_review_activity_follows_company_officer_reassignment(self):
        request = self._make_request()
        request.with_user(self.user).action_submit()

        self.company.sudo().sedar_procurement_inventory_officer_id = self.other_officer

        activities = request._open_review_activities()
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.other_officer)

    def test_review_deadline_uses_assigned_officer_timezone(self):
        self.officer.tz = "Asia/Manila"
        request = self._make_request(required_date=datetime(2026, 9, 8, 16, 30, 0))

        request.with_user(self.user).action_submit()

        self.assertEqual(request._open_review_activities().date_deadline, date(2026, 9, 9))

    def test_invalid_officer_configuration_blocks_submission(self):
        request = self._make_request()
        self.company.sudo().sedar_procurement_inventory_officer_id = False
        with self.assertRaisesRegex(UserError, "Configure an active Procurement and Inventory Officer"):
            request.with_user(self.user).action_submit()

        with self.assertRaises(ValidationError):
            self.company.sudo().sedar_procurement_inventory_officer_id = self.user

    def test_access_groups_preserve_least_privilege_and_legacy_officer_assignments(self):
        self.assertFalse(self.user.has_group("purchase.group_purchase_user"))

        request_user_group = self.env.ref(
            "sedar_purchase_request.group_sedar_purchase_request_user"
        )
        inventory_officer_group = self.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        sentinel = self.env["res.groups"].create({
            "name": "Unrelated Addon Implication",
        })
        request_user_group.write({
            "implied_ids": [Command.link(
                self.env.ref("purchase.group_purchase_user").id
            )],
        })
        inventory_officer_group.write({
            "implied_ids": [Command.link(sentinel.id)],
        })

        convert_file(
            self.env,
            "sedar_purchase_request",
            "security/sedar_purchase_request_security.xml",
            {},
            mode="update",
            noupdate=False,
        )

        self.assertNotIn(
            self.env.ref("purchase.group_purchase_user"),
            request_user_group.implied_ids,
        )
        self.assertIn(sentinel, inventory_officer_group.implied_ids)

        legacy_officer = self.env["res.users"].create({
            "name": "Legacy Procurement Officer",
            "login": "legacy.procurement.officer@test.example",
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
            "group_ids": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref(
                    "sedar_purchase_request.group_sedar_purchase_request_manager"
                ).id,
            ])],
        })

        self.assertTrue(legacy_officer.has_group(
            "sedar_marine_inventory.group_marine_inventory_manager"
        ))
        self.assertTrue(legacy_officer.has_group("purchase.group_purchase_manager"))
        self.assertTrue(legacy_officer.has_group("stock.group_stock_manager"))

    def test_workflow_audit_and_submitted_facts_cannot_be_forged(self):
        request = self._make_request()
        forged = request.with_user(self.user).with_context(sedar_purchase_request_action=True)
        with self.assertRaises(AccessError):
            forged.write({"state": "approved", "approved_by_id": self.user.id})

        request.with_user(self.user).action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.user).with_context(sedar_purchase_request_action=True).write({
                "justification": "Silently changed after review began."
            })
        with self.assertRaises(AccessError):
            request.line_ids.with_user(self.user).write({"quantity": 99})
        with self.assertRaises(AccessError):
            self.env["sedar.purchase.request.line"].with_user(self.user).create({
                "request_id": request.id, "product_id": self.product.id, "quantity": 1,
            })
        with self.assertRaises(AccessError):
            request.line_ids.with_user(self.user).unlink()

    def test_other_requester_cannot_submit_or_edit_draft(self):
        request = self._make_request()
        outsider = self.env["res.users"].create({
            "name": "Other Requester", "login": "other.requester@test.example",
            "company_id": self.company.id, "company_ids": [(6, 0, [self.company.id])],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("sedar_purchase_request.group_sedar_purchase_request_user").id,
            ])],
        })
        with self.assertRaises(AccessError):
            request.with_user(outsider).action_submit()
        with self.assertRaises(AccessError):
            request.with_user(outsider).write({"justification": "Changed by someone else."})
        with self.assertRaises(AccessError):
            request.line_ids.with_user(outsider).write({"quantity": 8})
        self.assertFalse(
            self.env["sedar.purchase.request"].with_user(outsider).search([("id", "=", request.id)])
        )
        self.assertEqual(
            self.env["sedar.purchase.request"].with_user(self.officer).search([("id", "=", request.id)]),
            request,
        )

    def test_requester_must_be_internal_and_allowed_in_request_company(self):
        other_company = self.env["res.company"].create({"name": "Other Request Company"})
        other_company_user = self.env["res.users"].create({
            "name": "Other Company Requester",
            "login": "other.company.requester@test.example",
            "company_id": other_company.id,
            "company_ids": [(6, 0, [other_company.id])],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("sedar_purchase_request.group_sedar_purchase_request_user").id,
            ])],
        })
        with self.assertRaises(ValidationError):
            self.env["sedar.purchase.request"].with_user(self.officer).create({
                "requester_id": other_company_user.id,
                "company_id": self.company.id,
                "required_date": datetime(2026, 9, 8, 8, 0, 0),
                "source_type": "manual",
                "justification": "Invalid cross-company requester.",
                "line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 1})],
            })

    def test_service_products_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "physical goods only"):
            self._make_request(line_ids=[(0, 0, {
                "product_id": self.service.id, "quantity": 1,
            })])
        with self.assertRaisesRegex(ValidationError, "physical goods only"):
            self._make_request(line_ids=[(0, 0, {
                "product_id": self.combo.id, "quantity": 1,
            })])

    def test_procurement_progress_supports_grouping(self):
        request = self._make_request()
        grouped = self.env["sedar.purchase.request"]._read_group(
            [("id", "=", request.id)],
            groupby=["procurement_progress"],
            aggregates=["__count"],
        )
        self.assertEqual(grouped, [("not_started", 1)])

    def test_maintenance_work_order_autocopies_equipment_and_rejects_mismatch(self):
        category = self.env["maintenance.equipment.category"].create({"name": "PR Equipment"})
        equipment = self.env["maintenance.equipment"].create({
            "name": "Main Engine A", "category_id": category.id, "company_id": self.company.id,
        })
        other = self.env["maintenance.equipment"].create({
            "name": "Main Engine B", "category_id": category.id, "company_id": self.company.id,
        })
        work_order = self.env["maintenance.request"].create({
            "name": "Inspect Main Engine", "equipment_id": equipment.id, "company_id": self.company.id,
            "sedar_work_order_type": "planned",
        })

        request = self._make_request(
            source_type="maintenance", maintenance_request_id=work_order.id,
        )
        self.assertEqual(request.equipment_id, equipment)
        with self.assertRaises(ValidationError):
            self._make_request(
                source_type="maintenance", maintenance_request_id=work_order.id,
                equipment_id=other.id,
            )

    def test_direct_rfq_is_deferred_to_bid_and_line_award(self):
        request = self._make_request()
        request.with_user(self.user).action_submit()
        request.with_user(self.officer).action_approve()
        with self.assertRaisesRegex(UserError, "Bids and Line Awards"):
            request.with_user(self.officer).action_create_rfq()

    def test_cancel_is_requester_or_officer_only_and_never_approved(self):
        request = self._make_request()
        with self.assertRaises(AccessError):
            request.with_user(self.other_officer).action_cancel()
        request.with_user(self.user).action_submit()
        request.with_user(self.user).action_cancel()
        self.assertEqual(request.state, "cancelled")

        approved = self._make_request()
        approved.with_user(self.user).action_submit()
        approved.with_user(self.officer).action_approve()
        with self.assertRaises(UserError):
            approved.with_user(self.officer).action_cancel()

    def test_multiple_purchase_orders_and_legacy_link_remain_accessible(self):
        request = self._make_request()
        order_1 = self.env["purchase.order"].sudo().create({
            "partner_id": self.supplier.id, "company_id": self.company.id,
            "sedar_purchase_request_id": request.id,
        })
        order_2 = self.env["purchase.order"].sudo().create({
            "partner_id": self.supplier.id, "company_id": self.company.id,
            "sedar_purchase_request_id": request.id,
        })
        request.invalidate_recordset(["purchase_order_ids", "purchase_order_count", "procurement_progress"])
        privileged_request = request.sudo()
        self.assertEqual(privileged_request.purchase_order_ids, order_1 | order_2)
        self.assertEqual(privileged_request.purchase_order_count, 2)
        self.assertEqual(privileged_request.procurement_progress, "ordering")
        domain_ids = request.with_user(self.officer).action_open_purchase_orders()["domain"][0][2]
        self.assertEqual(set(domain_ids), set((order_1 | order_2).ids))

        legacy_request = self._make_request()
        legacy_order = self.env["purchase.order"].sudo().create({
            "partner_id": self.supplier.id, "company_id": self.company.id,
        })
        legacy_request.sudo().purchase_order_id = legacy_order
        self.assertEqual(legacy_request.purchase_order_count, 1)
        self.assertEqual(legacy_request.with_user(self.officer).action_open_purchase_orders()["res_id"], legacy_order.id)

    def test_purchase_order_link_cannot_be_forged(self):
        request = self._make_request()
        with self.assertRaises(AccessError):
            self.env["purchase.order"].with_user(self.officer).create({
                "partner_id": self.supplier.id,
                "company_id": self.company.id,
                "sedar_purchase_request_id": request.id,
            })

    def test_legacy_order_migration_is_idempotent(self):
        request = self._make_request()
        order = self.env["purchase.order"].create({
            "partner_id": self.supplier.id, "company_id": self.company.id,
        })
        request.sudo().purchase_order_id = order
        self.env.flush_all()
        migration_path = Path(get_module_path("sedar_purchase_request")) / "migrations/19.0.2.0.0/post-migrate.py"
        spec = importlib.util.spec_from_file_location("sedar_purchase_request_post_migrate", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        migration.migrate(self.env.cr, "19.0.1.0.0")
        migration.migrate(self.env.cr, "19.0.1.0.0")
        order.invalidate_recordset(["sedar_purchase_request_id"])

        self.assertEqual(order.sedar_purchase_request_id, request)
        self.assertEqual(request.purchase_order_id, order)

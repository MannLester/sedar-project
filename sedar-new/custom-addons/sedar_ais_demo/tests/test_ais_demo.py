import base64
import json

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSedarAisDemo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.sedar_ensure_ais_demo()
        cls.tug = cls.env["sedar.tugboat"].search([
            ("company_id", "=", cls.env.company.id), ("ais_position_ids", "!=", False),
        ], limit=1)
        cls.equipment = cls.env["maintenance.equipment"].create({
            "name": "Issue 8 Main Engine",
            "company_id": cls.env.company.id,
            "sedar_tugboat_id": cls.tug.id,
            "sedar_system": "propulsion",
            "sedar_criticality": "critical",
        })
        cls.empty_equipment = cls.env["maintenance.equipment"].create({
            "name": "Issue 8 Empty Equipment",
            "company_id": cls.env.company.id,
            "sedar_tugboat_id": cls.tug.id,
        })
        ais_group = cls.env.ref("sedar_ais_demo.group_sedar_ais_user")
        officer_group = cls.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        cls.ais_user = cls._create_user("issue8-ais", [ais_group])
        cls.no_ais_user = cls._create_user("issue8-no-ais", [])
        cls.officer = cls._create_user(
            "issue8-officer", [ais_group, officer_group]
        )
        cls.generic_manager = cls._create_user(
            "issue8-manager", [ais_group, officer_group]
        )
        cls.env.company.sedar_procurement_inventory_officer_id = cls.officer
        cls.product = cls.env["product.product"].create({
            "name": "Issue 8 Protected Product",
            "is_storable": True,
        })
        cls.request = cls.env["sedar.purchase.request"].sudo().create({
            "requester_id": cls.ais_user.id,
            "company_id": cls.env.company.id,
            "currency_id": cls.env.company.currency_id.id,
            "equipment_id": cls.equipment.id,
            "justification": "Issue 8 operational need",
            "state": "draft",
        })
        cls.line = cls.env["sedar.purchase.request.line"].sudo().create({
            "request_id": cls.request.id,
            "product_id": cls.product.id,
            "quantity": 2,
        })
        cls.request.sudo().write({"state": "approved"})
        cls.bidder = cls.env["res.partner"].create({
            "name": "ISSUE8 SECRET SUPPLIER",
            "supplier_rank": 1,
            "company_id": cls.env.company.id,
        })
        cls.bid = cls.env["sedar.purchase.bid"].sudo().create({
            "name": "ISSUE8 SECRET BID",
            "request_id": cls.request.id,
            "bidder_id": cls.bidder.id,
            "state": "received",
            "capture_source": "manual",
            "received_by_id": cls.officer.id,
            "received_at": fields.Datetime.now(),
            "received_date": "2026-08-01",
            "validity_date": "2026-09-02",
            "promised_delivery_date": "2026-09-15",
            "quotation_file": base64.b64encode(b"ISSUE8 SECRET ATTACHMENT"),
            "quotation_filename": "issue8-secret-quote.pdf",
            "delivery_terms": "ISSUE8 SECRET DELIVERY TERMS",
            "availability_notes": "ISSUE8 SECRET AVAILABILITY",
            "payment_terms": "ISSUE8 SECRET TERMS",
            "warranty_notes": "ISSUE8 SECRET WARRANTY",
            "commercial_notes": "ISSUE8 SECRET COMMERCIAL NOTES",
        })
        cls.bid_line = cls.env["sedar.purchase.bid.line"].sudo().create({
            "bid_id": cls.bid.id,
            "request_line_id": cls.line.id,
            "quantity": 2,
            "unit_price": 987654.321,
            "promised_delivery_date": "2026-09-10",
            "availability_note": "ISSUE8 SECRET LINE AVAILABILITY",
            "delivery_terms": "ISSUE8 SECRET LINE DELIVERY",
            "notes": "ISSUE8 SECRET LINE NOTES",
        })
        cls.award = cls.env["sedar.purchase.line.award"].sudo().with_context(
            sedar_award_workflow=True
        ).create({
            "request_id": cls.request.id,
            "request_line_id": cls.line.id,
            "active_request_line_id": cls.line.id,
            "bid_id": cls.bid.id,
            "bid_line_id": cls.bid_line.id,
            "bidder_id": cls.bidder.id,
            "company_id": cls.env.company.id,
            "currency_id": cls.env.company.currency_id.id,
            "product_id": cls.product.id,
            "product_uom_id": cls.product.uom_id.id,
            "quantity": 2,
            "unit_price": 987654.321,
            "award_reason": "ISSUE8 SECRET AWARD REASON",
            "awarded_by_id": cls.officer.id,
            "awarded_at": fields.Datetime.now(),
        })
        cls.line.sudo().with_context(sedar_award_workflow=True).write({
            "current_award_id": cls.award.id,
        })

    @classmethod
    def _create_user(cls, login, groups):
        return cls.env["res.users"].create({
            "name": login,
            "login": f"{login}@example.test",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set(cls.env.company.ids)],
            "group_ids": [Command.set([group.id for group in groups])],
        })

    def test_dashboard_payload_exposes_simulation_and_crew(self):
        payload = self.env["sedar.ais.position"].get_dashboard_data()
        self.assertTrue(payload["simulation"])
        self.assertTrue(payload["fleet"])
        self.assertTrue(all("crew" in tug and "status" in tug for tug in payload["fleet"]))
        tug = next(item for item in payload["fleet"] if item["id"] == self.tug.id)
        equipment = next(item for item in tug["equipment"] if item["id"] == self.equipment.id)
        self.assertEqual(equipment["system"], "propulsion")
        self.assertEqual(equipment["criticality"], "critical")
        self.assertEqual(equipment["active_procurement_count"], 1)

    def test_limited_detail_recursively_omits_commercial_values(self):
        detail = self.env["sedar.ais.position"].with_user(
            self.ais_user
        ).get_equipment_procurement_detail(self.equipment.id)
        self.assertEqual(detail["access"], "limited")
        self.assertTrue(detail["active_procurement"])
        serialized = json.dumps(detail)
        for protected in (
            "ISSUE8 SECRET SUPPLIER", "ISSUE8 SECRET BID", "987654.321",
            "ISSUE8 SECRET AWARD REASON", "ISSUE8 SECRET TERMS",
            "ISSUE8 SECRET WARRANTY", "issue8-secret-quote.pdf", "attachment",
            "2026-08-01", "2026-09-02", "2026-09-15",
            "2026-09-10",
            "ISSUE8 SECRET DELIVERY TERMS", "ISSUE8 SECRET AVAILABILITY",
            "ISSUE8 SECRET COMMERCIAL NOTES", "ISSUE8 SECRET LINE AVAILABILITY",
            "ISSUE8 SECRET LINE DELIVERY", "ISSUE8 SECRET LINE NOTES",
            "supplier", "bidder", "price", "warranty", "url", "token",
        ):
            self.assertNotIn(protected.lower(), serialized.lower())

    def test_only_exact_officer_receives_allowlisted_commercial_summary(self):
        model = self.env["sedar.ais.position"]
        manager_detail = model.with_user(
            self.generic_manager
        ).get_equipment_procurement_detail(self.equipment.id)
        self.assertEqual(manager_detail["access"], "limited")
        detail = model.with_user(self.officer).get_equipment_procurement_detail(
            self.equipment.id
        )
        self.assertEqual(detail["access"], "full")
        commercial = detail["active_procurement"][0]["commercial"]
        bid = commercial["bids"][0]
        self.assertEqual(bid["bid_name"], self.bid.name)
        self.assertEqual(bid["bidder_name"], self.bidder.name)
        self.assertEqual(bid["quantity"], 2)
        self.assertEqual(bid["unit_price"], 987654.321)
        self.assertEqual(bid["received_date"], "2026-08-01")
        self.assertEqual(bid["validity_date"], "2026-09-02")
        self.assertEqual(bid["promised_delivery_date"], "2026-09-15")
        self.assertEqual(bid["line_promised_delivery_date"], "2026-09-10")
        self.assertEqual(bid["delivery_terms"], "ISSUE8 SECRET DELIVERY TERMS")
        self.assertEqual(bid["line_delivery_terms"], "ISSUE8 SECRET LINE DELIVERY")
        self.assertEqual(bid["availability_notes"], "ISSUE8 SECRET AVAILABILITY")
        self.assertEqual(
            bid["line_availability_notes"], "ISSUE8 SECRET LINE AVAILABILITY"
        )
        self.assertEqual(bid["payment_terms"], "ISSUE8 SECRET TERMS")
        self.assertEqual(bid["warranty_notes"], "ISSUE8 SECRET WARRANTY")
        self.assertEqual(bid["commercial_notes"], "ISSUE8 SECRET COMMERCIAL NOTES")
        self.assertEqual(bid["line_notes"], "ISSUE8 SECRET LINE NOTES")
        self.assertEqual(bid["attachment"]["name"], "issue8-secret-quote.pdf")
        self.assertIn("/web/content/", bid["attachment"]["action"]["url"])
        self.assertEqual(commercial["award"]["reason"], self.award.award_reason)
        self.assertNotIn("ISSUE8 SECRET ATTACHMENT", json.dumps(detail))

    def test_detail_denies_guessed_and_cross_company_equipment_ids(self):
        model = self.env["sedar.ais.position"].with_user(self.ais_user)
        with self.assertRaises(AccessError):
            model.get_equipment_procurement_detail(2147483647)
        other_company = self.env["res.company"].create({"name": "Issue 8 Other Company"})
        other_tug = self.env["sedar.tugboat"].with_company(other_company).create({
            "name": "Issue 8 Other Tug",
            "company_id": other_company.id,
            "registration_number": "ISSUE8-OTHER-TUG",
            "tug_class_id": self.tug.tug_class_id.id,
        })
        self.env["sedar.ais.position"].create({
            "tugboat_id": other_tug.id,
            "latitude": 13.75,
            "longitude": 121.0,
            "course_degrees": 1,
            "location_label": "Other company",
        })
        other_equipment = self.env["maintenance.equipment"].with_company(
            other_company
        ).create({
            "name": "Issue 8 Other Equipment",
            "company_id": other_company.id,
            "sedar_tugboat_id": other_tug.id,
        })
        with self.assertRaises(AccessError):
            model.get_equipment_procurement_detail(other_equipment.id)

    def test_both_rpc_methods_require_ais_access(self):
        model = self.env["sedar.ais.position"].with_user(self.no_ais_user)
        with self.assertRaises(AccessError):
            model.get_dashboard_data()
        with self.assertRaises(AccessError):
            model.get_equipment_procurement_detail(self.equipment.id)

    def test_detail_empty_state_and_dashboard_query_bound(self):
        detail = self.env["sedar.ais.position"].with_user(
            self.ais_user
        ).get_equipment_procurement_detail(self.empty_equipment.id)
        self.assertEqual(detail["active_procurement"], [])
        self.assertEqual(detail["procurement_history"], [])
        self.env.invalidate_all()
        before = self.env.cr.sql_log_count
        self.env["sedar.ais.position"].get_dashboard_data()
        self.assertLessEqual(self.env.cr.sql_log_count - before, 45)

    def test_cancelled_purchase_order_is_retained_in_history(self):
        self.request.with_user(self.officer).action_create_purchase_orders()
        order = self.request.sudo().purchase_order_ids
        self.assertEqual(len(order), 1)
        order.sudo().button_cancel()
        detail = self.env["sedar.ais.position"].with_user(
            self.officer
        ).get_equipment_procurement_detail(self.equipment.id)
        self.assertEqual(detail["active_procurement"], [])
        row = detail["procurement_history"][0]
        self.assertEqual(row["outcome"], "cancelled")
        self.assertEqual(row["commercial"]["orders"][0]["state"], "cancel")

    def test_simulation_advance_moves_an_underway_tug(self):
        self.env.company.sedar_ensure_ais_demo()
        position = self.env["sedar.ais.position"].search([
            ("navigation_status", "=", "underway"),
        ], limit=1)
        self.assertTrue(position)
        before = (position.latitude, position.longitude)
        self.env["sedar.ais.position"].action_advance_simulation()
        self.assertNotEqual(before, (position.latitude, position.longitude))

    def test_rejects_impossible_coordinates(self):
        tug = self.env["sedar.tugboat"].search([], limit=1)
        existing = self.env["sedar.ais.position"].search([("tugboat_id", "=", tug.id)], limit=1)
        if existing:
            with self.assertRaises(ValidationError):
                existing.latitude = 95

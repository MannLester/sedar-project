import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from psycopg2.errors import SerializationFailure

from odoo import Command, api, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.registry import Registry
from odoo.tests import BaseCase, TransactionCase, get_db_name, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestSedarPurchaseAward(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        base_group = cls.env.ref("base.group_user")
        request_group = cls.env.ref(
            "sedar_purchase_request.group_sedar_purchase_request_user"
        )
        officer_group = cls.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        cls.requester = cls.env["res.users"].create({
            "name": "Award Requester",
            "login": "award.requester@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([base_group.id, request_group.id])],
        })
        cls.officer = cls.env["res.users"].create({
            "name": "Configured Award Officer",
            "login": "configured.award.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([
                base_group.id, request_group.id, officer_group.id,
            ])],
        })
        cls.other_officer = cls.env["res.users"].create({
            "name": "Unconfigured Award Officer",
            "login": "unconfigured.award.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([
                base_group.id, request_group.id, officer_group.id,
            ])],
        })
        cls.company.sudo().sedar_procurement_inventory_officer_id = cls.officer
        cls.suppliers = cls.env["res.partner"].create([
            {"name": "Award Bidder One", "supplier_rank": 1},
            {"name": "Award Bidder Two", "supplier_rank": 1},
            {"name": "Award Bidder Three", "supplier_rank": 1},
        ])
        cls.products = cls.env["product.product"].create([
            {
                "name": "Award Product A",
                "type": "consu",
                "is_storable": True,
                "supplier_taxes_id": [Command.clear()],
            },
            {
                "name": "Award Product B",
                "type": "consu",
                "is_storable": True,
                "supplier_taxes_id": [Command.clear()],
            },
            {
                "name": "Award Product C",
                "type": "consu",
                "is_storable": True,
                "supplier_taxes_id": [Command.clear()],
            },
        ])

    def _make_request(
        self,
        products=None,
        required_date=None,
        *,
        company=None,
        requester=None,
        officer=None,
    ):
        products = products or self.products
        company = company or self.company
        requester = requester or self.requester
        officer = officer or self.officer
        request = self.env["sedar.purchase.request"].with_user(requester).create({
            "company_id": company.id,
            "required_date": required_date or datetime.combine(
                fields.Date.today() + timedelta(days=30), datetime.min.time()
            ),
            "source_type": "manual",
            "justification": "Compare supplier Bids and award each product.",
            "line_ids": [
                Command.create({
                    "product_id": product.id,
                    "quantity": index + 1,
                    "estimated_unit_price": 100.0,
                })
                for index, product in enumerate(products)
            ],
        })
        request.with_user(requester).action_submit()
        request.with_user(officer).action_approve()
        return request

    def _make_bid(
        self,
        request,
        supplier,
        request_lines,
        prices,
        *,
        received=True,
        validity_date=None,
        officer=None,
    ):
        officer = officer or self.officer
        today = fields.Date.today()
        bid = self.env["sedar.purchase.bid"].with_user(officer).create({
            "request_id": request.id,
            "bidder_id": supplier.id,
            "received_date": today - timedelta(days=10),
            "validity_date": validity_date or today + timedelta(days=30),
            "promised_delivery_date": today + timedelta(days=15),
            "quotation_filename": "award-quotation.txt",
            "quotation_file": base64.b64encode(b"private award quotation"),
            "line_ids": [
                Command.create({
                    "request_line_id": request_line.id,
                    "unit_price": price,
                })
                for request_line, price in zip(request_lines, prices)
            ],
        })
        if received:
            bid.with_user(officer).action_receive()
        return bid

    def _award(
        self, request_line, bid_line, reason="Best overall value", *, officer=None,
    ):
        return request_line.with_user(officer or self.officer)._create_line_award(
            bid_line, reason
        )

    def _make_multi_bidder_multi_supplier_award_scenario(self):
        request = self._make_request()
        lines = request.line_ids.sorted("sequence")
        bidder_one = self._make_bid(
            request, self.suppliers[0], lines[:2], [90.0, 180.0]
        )
        self._make_bid(request, self.suppliers[1], lines[:1], [85.0])
        bidder_three = self._make_bid(
            request, self.suppliers[2], lines[1:], [175.0, 270.0]
        )
        self._award(lines[0], bidder_one.line_ids.filtered(
            lambda line: line.request_line_id == lines[0]
        ), "Better delivery and warranty than the lower-priced offer.")
        self._award(lines[1], bidder_one.line_ids.filtered(
            lambda line: line.request_line_id == lines[1]
        ), "Best combined commercial terms for Product B.")
        self._award(lines[2], bidder_three.line_ids.filtered(
            lambda line: line.request_line_id == lines[2]
        ), "Only conforming full-quantity offer for Product C.")
        return request, lines, bidder_one, bidder_three

    def test_multi_supplier_awards_create_two_draft_orders_and_retry_is_idempotent(self):
        request, lines, bidder_one, bidder_three = (
            self._make_multi_bidder_multi_supplier_award_scenario()
        )

        request.with_user(self.officer).action_create_purchase_orders()
        orders = request.sudo().purchase_order_ids
        original_ids = set(orders.ids)

        self.assertEqual(len(orders), 2)
        self.assertEqual(set(orders.mapped("state")), {"draft"})
        order_one = orders.filtered(lambda order: order.sedar_bid_id == bidder_one)
        order_three = orders.filtered(lambda order: order.sedar_bid_id == bidder_three)
        self.assertEqual(order_one.partner_id, self.suppliers[0])
        self.assertEqual(order_three.partner_id, self.suppliers[2])
        self.assertEqual(set(order_one.order_line.product_id.ids), set(self.products[:2].ids))
        self.assertEqual(set(order_three.order_line.product_id.ids), set(self.products[2:].ids))
        self.assertEqual(
            set(order_one.order_line.sedar_purchase_request_line_id.ids),
            set(lines[:2].ids),
        )
        self.assertEqual(
            set(order_three.order_line.sedar_purchase_request_line_id.ids),
            set(lines[2:].ids),
        )
        prices_by_product = {
            order_line.product_id: order_line.price_unit
            for order_line in orders.order_line
        }
        self.assertEqual(prices_by_product, {
            self.products[0]: 90.0,
            self.products[1]: 180.0,
            self.products[2]: 270.0,
        })
        self.assertEqual(request.state, "po_created")
        self.assertTrue(all(
            award.state == "ordered" and award.purchase_order_line_id
            for award in request.sudo().award_ids
        ))

        request.with_user(self.officer).action_create_purchase_orders()
        self.assertEqual(set(request.sudo().purchase_order_ids.ids), original_ids)
        self.assertEqual(len(request.sudo().purchase_order_ids), 2)

    def test_award_requires_received_matching_bid_line_and_reason(self):
        request = self._make_request(products=self.products[:2])
        lines = request.line_ids.sorted("sequence")
        draft_bid = self._make_bid(
            request, self.suppliers[0], lines[:1], [10.0], received=False
        )
        other_bid = self._make_bid(
            request, self.suppliers[1], lines[1:], [20.0]
        )

        with self.assertRaisesRegex(UserError, "Received Bid"):
            with self.env.cr.savepoint():
                self._award(lines[0], draft_bid.line_ids)
        with self.assertRaisesRegex(ValidationError, "this Purchase Request product"):
            with self.env.cr.savepoint():
                self._award(lines[0], other_bid.line_ids)

        draft_bid.with_user(self.officer).action_receive()
        with self.assertRaisesRegex(UserError, "best-value reason"):
            with self.env.cr.savepoint():
                self._award(lines[0], draft_bid.line_ids, "   ")

    def test_reset_requires_reason_preserves_history_and_allows_reaward(self):
        request = self._make_request(products=self.products[:1])
        line = request.line_ids
        first = self._make_bid(request, self.suppliers[0], line, [10.0])
        second = self._make_bid(request, self.suppliers[1], line, [12.0])
        award = self._award(line, first.line_ids)

        with self.assertRaisesRegex(UserError, "reason for resetting"):
            with self.env.cr.savepoint():
                award.with_user(self.officer)._reset_with_reason(" ")
        award.with_user(self.officer)._reset_with_reason("Delivery date changed.")
        replacement = self._award(
            line, second.line_ids, "More reliable revised delivery commitment."
        )

        self.assertEqual(award.state, "reset")
        self.assertEqual(award.reset_by_id, self.officer)
        self.assertEqual(award.reset_reason, "Delivery date changed.")
        self.assertEqual(line.sudo().current_award_id, replacement)
        self.assertEqual(len(line.sudo().award_history_ids), 2)

    def test_line_with_reset_award_history_cannot_be_cancelled(self):
        request = self._make_request(products=self.products[:1])
        line = request.line_ids
        bid = self._make_bid(request, self.suppliers[0], line, [10.0])
        award = self._award(line, bid.line_ids)
        award.with_user(self.officer)._reset_with_reason("Supplier revised its offer.")

        with self.assertRaisesRegex(UserError, "no Line Award history"):
            with self.env.cr.savepoint():
                line.with_user(self.officer).action_open_cancel_wizard()
        with self.assertRaisesRegex(UserError, "no Line Award history"):
            with self.env.cr.savepoint():
                line.with_user(self.officer)._cancel_for_procurement(
                    "Requirement withdrawn after award reset."
                )

        self.assertEqual(line.line_state, "active")
        self.assertFalse(line.sudo().current_award_id)
        self.assertEqual(line.sudo().award_history_ids, award)

    def test_line_cancellation_requires_unawarded_line_and_excludes_it_from_handoff(self):
        request = self._make_request(products=self.products[:2])
        lines = request.line_ids.sorted("sequence")
        bid = self._make_bid(request, self.suppliers[0], lines[:1], [25.0])
        self._award(lines[0], bid.line_ids)

        with self.assertRaisesRegex(UserError, "reason for cancelling"):
            with self.env.cr.savepoint():
                lines[1].with_user(self.officer)._cancel_for_procurement(" ")
        lines[1].with_user(self.officer)._cancel_for_procurement(
            "Requirement withdrawn before ordering."
        )
        with self.assertRaisesRegex(UserError, "award or is cancelled"):
            with self.env.cr.savepoint():
                self._award(lines[1], bid.line_ids)
        request.with_user(self.officer).action_create_purchase_orders()

        self.assertEqual(lines[1].line_state, "cancelled")
        self.assertEqual(lines[1].cancelled_by_id, self.officer)
        self.assertEqual(len(request.sudo().purchase_order_ids), 1)
        self.assertEqual(
            request.sudo().purchase_order_ids.order_line.product_id,
            self.products[:1],
        )

    def test_zero_price_requires_confirmation_and_is_preserved_on_order(self):
        request = self._make_request(products=self.products[:1])
        line = request.line_ids
        bid = self._make_bid(request, self.suppliers[0], line, [0.0])

        with self.assertRaisesRegex(UserError, "zero unit price"):
            with self.env.cr.savepoint():
                self._award(line, bid.line_ids)
        award = line.with_user(self.officer)._create_line_award(
            bid.line_ids, "Supplier replacement under warranty.",
            zero_price_confirmed=True,
        )
        request.with_user(self.officer).action_create_purchase_orders()

        self.assertTrue(award.zero_price_confirmed)
        self.assertEqual(award.purchase_order_line_id.price_unit, 0.0)

    def test_expired_bid_requires_reasoned_override(self):
        request = self._make_request(products=self.products[:1])
        line = request.line_ids
        bid = self._make_bid(
            request,
            self.suppliers[0],
            line,
            [50.0],
            validity_date=fields.Date.today() - timedelta(days=1),
        )

        with self.assertRaisesRegex(UserError, "expired Bid"):
            with self.env.cr.savepoint():
                self._award(line, bid.line_ids)
        with self.assertRaisesRegex(UserError, "expired Bid"):
            with self.env.cr.savepoint():
                line.with_user(self.officer)._create_line_award(
                    bid.line_ids, "Still the best operational option.",
                    expired_override=True,
                )
        award = line.with_user(self.officer)._create_line_award(
            bid.line_ids,
            "Still the best operational option.",
            expired_override=True,
            expired_override_reason="Supplier reconfirmed the quotation today.",
        )

        self.assertTrue(award.expired_bid_override)
        self.assertEqual(
            award.expired_bid_override_reason,
            "Supplier reconfirmed the quotation today.",
        )

    def test_generated_order_sources_and_facts_are_immutable(self):
        request, _lines, _bidder_one, _bidder_three = (
            self._make_multi_bidder_multi_supplier_award_scenario()
        )
        request.with_user(self.officer).action_create_purchase_orders()
        order = request.sudo().purchase_order_ids[:1]
        order_line = order.order_line[:1]

        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                order.with_user(self.officer).write({"partner_id": self.suppliers[2].id})
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                order_line.with_user(self.officer).write({"price_unit": 999.0})
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                order_line.with_user(self.officer).write({"sedar_bid_line_id": False})
        with self.assertRaisesRegex(UserError, "cannot be deleted"):
            with self.env.cr.savepoint():
                order.with_user(self.officer).unlink()

    def test_bid_with_reset_award_history_cannot_withdraw_and_ordered_award_cannot_reset(self):
        request = self._make_request(products=self.products[:1])
        line = request.line_ids
        first_bid = self._make_bid(request, self.suppliers[0], line, [40.0])
        second_bid = self._make_bid(request, self.suppliers[1], line, [42.0])
        reset_award = self._award(line, first_bid.line_ids)
        reset_award.with_user(self.officer)._reset_with_reason(
            "Supplier revised the quotation."
        )
        first_bid.with_user(self.officer).withdrawal_reason = (
            "Supplier requested withdrawal."
        )

        with self.assertRaisesRegex(UserError, "Line Award history"):
            with self.env.cr.savepoint():
                first_bid.with_user(self.officer).action_withdraw()
        award = self._award(line, second_bid.line_ids)
        request.with_user(self.officer).action_create_purchase_orders()
        with self.assertRaisesRegex(UserError, "after Purchase Order handoff"):
            with self.env.cr.savepoint():
                award.with_user(self.officer)._reset_with_reason("Try another supplier.")

    def test_generated_order_notes_include_winning_terms_without_chatter_leak(self):
        request = self._make_request(products=self.products[:1])
        bid = self._make_bid(
            request,
            self.suppliers[0],
            request.line_ids,
            [75.0],
            received=False,
        )
        bid.with_user(self.officer).write({
            "delivery_terms": "Header delivery FOB Cebu",
            "availability_notes": "Header availability: in stock",
            "payment_terms": "Header payment: net 30",
            "warranty_notes": "Header warranty: two years",
            "commercial_notes": "Header commercial note",
        })
        bid.line_ids.with_user(self.officer).write({
            "availability_note": "Winning line available now",
            "delivery_terms": "Winning line delivered alongside vessel",
            "notes": "Winning line note <script>alert('unsafe')</script>",
        })
        bid.with_user(self.officer).action_receive()
        self._award(request.line_ids, bid.line_ids)

        request.with_user(self.officer).action_create_purchase_orders()
        order_note = str(request.sudo().purchase_order_ids.note)
        request_chatter = "\n".join(
            str(body) for body in request.sudo().message_ids.mapped("body")
        )

        for expected in (
            "Header delivery FOB Cebu",
            "Header availability: in stock",
            "Header payment: net 30",
            "Header warranty: two years",
            "Header commercial note",
            "Winning line available now",
            "Winning line delivered alongside vessel",
            "Winning line note",
        ):
            self.assertIn(expected, order_note)
            self.assertNotIn(expected, request_chatter)
        self.assertNotIn("<script>", order_note)
        self.assertIn("&lt;script&gt;", order_note)

    def test_only_exact_configured_officer_can_award_or_read_awards(self):
        request = self._make_request(products=self.products[:1])
        line = request.line_ids
        bid = self._make_bid(request, self.suppliers[0], line, [40.0])

        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                line.with_user(self.other_officer)._create_line_award(
                    bid.line_ids, "Unauthorized choice."
                )
        award = self._award(line, bid.line_ids)
        self.assertFalse(
            self.env["sedar.purchase.line.award"].with_user(
                self.other_officer
            ).search([("id", "=", award.id)])
        )
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                award.with_user(self.requester).read(["unit_price", "award_reason"])
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                request.with_user(self.other_officer).action_create_purchase_orders()

    def test_legacy_incomplete_handoff_requires_audited_recovery(self):
        request = self._make_request(products=self.products[:1])
        request.sudo().write({"state": "po_created"})
        self.assertTrue(request.legacy_handoff_recovery_required)

        with self.assertRaisesRegex(UserError, "reason for recovering"):
            with self.env.cr.savepoint():
                request.with_user(self.officer)._recover_legacy_handoff(" ")
        request.with_user(self.officer)._recover_legacy_handoff(
            "The historic handoff has no linked Purchase Order."
        )

        self.assertEqual(request.state, "approved")
        self.assertFalse(request.legacy_handoff_recovery_required)
        self.assertEqual(request.handoff_recovered_by_id, self.officer)
        self.assertTrue(request.handoff_recovered_at)
        self.assertEqual(
            request.handoff_recovery_reason,
            "The historic handoff has no linked Purchase Order.",
        )

    def test_supplierinfo_does_not_overwrite_awarded_order_line_facts(self):
        product = self.products[0]
        supplier = self.suppliers[0]
        dozen_uom = self.env.ref("uom.product_uom_dozen")
        self.env["product.supplierinfo"].create({
            "partner_id": supplier.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_id": product.id,
            "product_uom_id": dozen_uom.id,
            "min_qty": 1.0,
            "price": 999.0,
            "delay": 90,
        })
        request = self._make_request(products=product)
        request_line = request.line_ids
        promised_date = fields.Date.today() + timedelta(days=7)
        bid = self._make_bid(
            request, supplier, request_line, [123.45], received=False
        )
        bid.line_ids.with_user(self.officer).promised_delivery_date = promised_date
        bid.with_user(self.officer).action_receive()
        award = self._award(request_line, bid.line_ids)

        request.with_user(self.officer).action_create_purchase_orders()
        order_line = award.sudo().purchase_order_line_id

        self.assertEqual(order_line.product_qty, award.quantity)
        self.assertEqual(order_line.product_uom_id, award.product_uom_id)
        self.assertEqual(order_line.price_unit, award.unit_price)
        self.assertEqual(fields.Date.to_date(order_line.date_planned), promised_date)

    def test_price_included_source_tax_blocks_before_fiscal_position_mapping(self):
        included_tax = self.env["account.tax"].create({
            "name": "Included source purchase tax",
            "amount": 12.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "price_include_override": "tax_included",
            "company_id": self.company.id,
        })
        excluded_tax = self.env["account.tax"].create({
            "name": "Excluded mapped purchase tax",
            "amount": 12.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "price_include_override": "tax_excluded",
            "company_id": self.company.id,
            "original_tax_ids": [Command.set(included_tax.ids)],
        })
        fiscal_position = self.env["account.fiscal.position"].create({
            "name": "Map included purchase tax to excluded tax",
            "company_id": self.company.id,
            "tax_ids": [Command.set(excluded_tax.ids)],
        })
        supplier = self.suppliers[0].with_company(self.company)
        supplier.property_account_position_id = fiscal_position
        product = self.products[0]
        product.supplier_taxes_id = [Command.set(included_tax.ids)]
        request = self._make_request(products=product)
        bid = self._make_bid(request, supplier, request.line_ids, [100.0])
        self._award(request.line_ids, bid.line_ids)

        selected_position = self.env["account.fiscal.position"]._get_fiscal_position(
            supplier
        )
        self.assertEqual(selected_position, fiscal_position)
        self.assertEqual(fiscal_position.map_tax(included_tax), excluded_tax)
        with self.assertRaisesRegex(UserError, "price-included supplier tax"):
            with self.env.cr.savepoint():
                request.with_user(self.officer).action_create_purchase_orders()

        self.assertFalse(request.sudo().purchase_order_ids)

    def test_required_datetime_fallback_is_preserved_exactly(self):
        required_datetime = datetime.combine(
            fields.Date.today() + timedelta(days=20),
            datetime.min.time().replace(hour=14, minute=35),
        )
        request = self._make_request(
            products=self.products[:1], required_date=required_datetime
        )
        bid = self._make_bid(
            request,
            self.suppliers[0],
            request.line_ids,
            [80.0],
            received=False,
        )
        bid.with_user(self.officer).promised_delivery_date = False
        bid.with_user(self.officer).action_receive()
        award = self._award(request.line_ids, bid.line_ids)

        request.with_user(self.officer).action_create_purchase_orders()

        self.assertEqual(
            award.sudo().purchase_order_line_id.date_planned,
            request.required_date,
        )

    def test_failure_in_later_supplier_group_rolls_back_all_orders(self):
        request, _lines, _bidder_one, _bidder_three = (
            self._make_multi_bidder_multi_supplier_award_scenario()
        )
        blocking_tax = self.env["account.tax"].create({
            "name": "Included tax on later supplier group",
            "amount": 5.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "price_include_override": "tax_included",
            "company_id": self.company.id,
        })
        self.products[2].supplier_taxes_id = [Command.set(blocking_tax.ids)]

        with self.assertRaisesRegex(UserError, "price-included supplier tax"):
            with self.env.cr.savepoint():
                request.with_user(self.officer).action_create_purchase_orders()

        request.invalidate_recordset()
        request.sudo().award_ids.invalidate_recordset()
        self.assertFalse(request.sudo().purchase_order_ids)
        self.assertEqual(request.state, "approved")
        self.assertTrue(all(
            award.state == "awarded" and not award.purchase_order_line_id
            for award in request.sudo().award_ids
        ))

    def test_generated_order_confirms_and_creates_linked_receipt(self):
        request = self._make_request(products=self.products[:1])
        bid = self._make_bid(
            request, self.suppliers[0], request.line_ids, [65.0]
        )
        award = self._award(request.line_ids, bid.line_ids)
        request.with_user(self.officer).action_create_purchase_orders()
        order = request.sudo().purchase_order_ids
        order_line = order.order_line
        source_ids = (
            order.sedar_purchase_request_id.id,
            order.sedar_bid_id.id,
            order_line.sedar_purchase_request_line_id.id,
            order_line.sedar_bid_line_id.id,
            order_line.sedar_line_award_id.id,
        )

        order.with_user(self.officer).button_confirm()
        if order.state == "to approve":
            order.with_user(self.officer).button_approve()

        self.assertEqual(order.state, "purchase")
        self.assertTrue(order.picking_ids)
        self.assertEqual(set(order.picking_ids.mapped("picking_type_code")), {"incoming"})
        self.assertEqual(source_ids, (
            order.sedar_purchase_request_id.id,
            order.sedar_bid_id.id,
            order_line.sedar_purchase_request_line_id.id,
            order_line.sedar_bid_line_id.id,
            order_line.sedar_line_award_id.id,
        ))
        self.assertEqual(award.sudo().purchase_order_line_id, order_line)

    def test_generated_order_can_cancel_and_reset_to_draft_without_losing_links(self):
        request = self._make_request(products=self.products[:1])
        bid = self._make_bid(
            request, self.suppliers[0], request.line_ids, [65.0]
        )
        award = self._award(request.line_ids, bid.line_ids)
        request.with_user(self.officer).action_create_purchase_orders()
        order = request.sudo().purchase_order_ids
        order_line = order.order_line
        source_links = (
            order.sedar_purchase_request_id,
            order.sedar_bid_id,
            order_line.sedar_purchase_request_line_id,
            order_line.sedar_bid_line_id,
            order_line.sedar_line_award_id,
        )

        order.with_user(self.officer).button_confirm()
        if order.state == "to approve":
            order.with_user(self.officer).button_approve()
        order.with_user(self.officer).button_cancel()
        order.with_user(self.officer).button_draft()

        self.assertEqual(order.state, "draft")
        self.assertEqual(source_links, (
            order.sedar_purchase_request_id,
            order.sedar_bid_id,
            order_line.sedar_purchase_request_line_id,
            order_line.sedar_bid_line_id,
            order_line.sedar_line_award_id,
        ))
        self.assertEqual(award.sudo().purchase_order_line_id, order_line)

    def test_generated_order_supports_standard_supplier_bill_creation(self):
        product = self.products[0]
        product.product_tmpl_id.purchase_method = "purchase"
        request = self._make_request(products=product)
        bid = self._make_bid(
            request, self.suppliers[0], request.line_ids, [65.0]
        )
        award = self._award(request.line_ids, bid.line_ids)
        request.with_user(self.officer).action_create_purchase_orders()
        order = request.sudo().purchase_order_ids
        order.with_user(self.officer).button_confirm()
        if order.state == "to approve":
            order.with_user(self.officer).button_approve()

        order.with_user(self.officer).action_create_invoice()
        bill = order.sudo().invoice_ids

        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(
            bill.invoice_line_ids.filtered("purchase_line_id").purchase_line_id,
            award.sudo().purchase_order_line_id,
        )
        self.assertEqual(order.sedar_purchase_request_id, request)
        self.assertEqual(order.sedar_bid_id, bid)

    def test_award_and_handoff_are_isolated_to_the_request_company(self):
        second_company = self.env["res.company"].create({
            "name": "Award Isolation Company",
            "currency_id": self.company.currency_id.id,
        })
        base_group = self.env.ref("base.group_user")
        request_group = self.env.ref(
            "sedar_purchase_request.group_sedar_purchase_request_user"
        )
        officer_group = self.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        requester = self.env["res.users"].create({
            "name": "Second Company Requester",
            "login": "award.second.requester@test.example",
            "company_id": second_company.id,
            "company_ids": [Command.set(second_company.ids)],
            "group_ids": [Command.set([base_group.id, request_group.id])],
        })
        officer = self.env["res.users"].create({
            "name": "Second Company Officer",
            "login": "award.second.officer@test.example",
            "company_id": second_company.id,
            "company_ids": [Command.set(second_company.ids)],
            "group_ids": [Command.set([
                base_group.id, request_group.id, officer_group.id,
            ])],
        })
        second_company.sudo().sedar_procurement_inventory_officer_id = officer
        supplier = self.env["res.partner"].create({
            "name": "Second Company Supplier",
            "supplier_rank": 1,
            "company_id": second_company.id,
        })
        product = self.env["product.product"].create({
            "name": "Second Company Award Product",
            "type": "consu",
            "company_id": second_company.id,
            "supplier_taxes_id": [Command.clear()],
        })
        request = self._make_request(
            products=product,
            company=second_company,
            requester=requester,
            officer=officer,
        )
        bid = self._make_bid(
            request, supplier, request.line_ids, [55.0], officer=officer
        )
        award = self._award(
            request.line_ids, bid.line_ids, officer=officer
        )

        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                request.with_user(self.officer).action_create_purchase_orders()
        self.assertFalse(
            self.env["sedar.purchase.line.award"].with_user(self.officer).search([
                ("id", "=", award.id),
            ])
        )

        request.with_user(officer).action_create_purchase_orders()
        order = request.sudo().purchase_order_ids
        self.assertEqual(order.company_id, second_company)
        self.assertEqual(order.currency_id, second_company.currency_id)
        self.assertEqual(order.sedar_purchase_request_id.company_id, second_company)
        self.assertEqual(order.sedar_bid_id.company_id, second_company)
        self.assertEqual(order.order_line.sedar_line_award_id.company_id, second_company)


@tagged("post_install", "-at_install")
class TestSedarPurchaseAwardConcurrency(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registry = Registry(get_db_name())
        with cls.registry.cursor() as cr:
            env = api.Environment(cr, api.SUPERUSER_ID, {})
            company = env["res.company"].create({
                "name": "Concurrent Award Company",
                "currency_id": env.company.currency_id.id,
            })
            base_group = env.ref("base.group_user")
            request_group = env.ref(
                "sedar_purchase_request.group_sedar_purchase_request_user"
            )
            officer_group = env.ref(
                "sedar_marine_inventory.group_marine_inventory_manager"
            )
            requester = env["res.users"].create({
                "name": "Concurrent Award Requester",
                "login": "concurrent.award.requester@test.example",
                "company_id": company.id,
                "company_ids": [Command.set(company.ids)],
                "group_ids": [Command.set([base_group.id, request_group.id])],
            })
            officer = env["res.users"].create({
                "name": "Concurrent Award Officer",
                "login": "concurrent.award.officer@test.example",
                "company_id": company.id,
                "company_ids": [Command.set(company.ids)],
                "group_ids": [Command.set([
                    base_group.id, request_group.id, officer_group.id,
                ])],
            })
            company.sedar_procurement_inventory_officer_id = officer
            supplier = env["res.partner"].create({
                "name": "Concurrent Award Supplier",
                "supplier_rank": 1,
                "company_id": company.id,
            })
            product = env["product.product"].create({
                "name": "Concurrent Award Product",
                "type": "consu",
                "company_id": company.id,
                "supplier_taxes_id": [Command.clear()],
            })
            request = env["sedar.purchase.request"].with_user(requester).create({
                "company_id": company.id,
                "required_date": datetime.combine(
                    fields.Date.today() + timedelta(days=30), datetime.min.time()
                ),
                "source_type": "manual",
                "justification": "Exercise concurrent grouped Purchase Order handoff.",
                "line_ids": [Command.create({
                    "product_id": product.id,
                    "quantity": 1.0,
                    "estimated_unit_price": 100.0,
                })],
            })
            request.with_user(requester).action_submit()
            request.with_user(officer).action_approve()
            bid = env["sedar.purchase.bid"].with_user(officer).create({
                "request_id": request.id,
                "bidder_id": supplier.id,
                "received_date": fields.Date.today(),
                "validity_date": fields.Date.today() + timedelta(days=30),
                "quotation_filename": "concurrent-quotation.txt",
                "quotation_file": base64.b64encode(b"concurrent quotation"),
                "line_ids": [Command.create({
                    "request_line_id": request.line_ids.id,
                    "unit_price": 95.0,
                })],
            })
            bid.with_user(officer).action_receive()
            request.line_ids.with_user(officer)._create_line_award(
                bid.line_ids, "Best concurrent award value."
            )
            cls.request_id = request.id
            cls.officer_id = officer.id

    @mute_logger("odoo.sql_db")
    def test_concurrent_handoff_creates_exactly_one_grouped_order(self):
        start = threading.Barrier(2)
        cursors = [self.registry.cursor() for _index in range(2)]
        environments = [
            api.Environment(cr, self.officer_id, {}) for cr in cursors
        ]

        def create_orders(env):
            request = env["sedar.purchase.request"].browse(self.request_id)
            retried = False
            try:
                env.cr.execute(
                    "SELECT id FROM sedar_purchase_request WHERE id = %s",
                    [self.request_id],
                )
                self.assertTrue(env.cr.fetchone())
                start.wait(timeout=10)
                request.action_create_purchase_orders()
            except SerializationFailure:
                retried = True
                env.cr.rollback()
                env.invalidate_all()
                request = env["sedar.purchase.request"].browse(self.request_id)
                request.action_create_purchase_orders()
            try:
                env.cr.commit()
                return request.sudo().purchase_order_ids.ids, retried
            except Exception:
                env.cr.rollback()
                raise

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(create_orders, env) for env in environments
                ]
                results = [future.result(timeout=20) for future in futures]
        finally:
            for cr in cursors:
                cr.close()

        with self.registry.cursor() as cr:
            env = api.Environment(cr, api.SUPERUSER_ID, {})
            request = env["sedar.purchase.request"].browse(self.request_id)
            self.assertEqual(len(request.purchase_order_ids), 1)
            self.assertEqual(
                [order_ids for order_ids, _retried in results],
                [request.purchase_order_ids.ids] * 2,
            )
            self.assertEqual(sum(retried for _order_ids, retried in results), 1)
            self.assertEqual(request.award_ids.purchase_order_line_id.order_id,
                             request.purchase_order_ids)

import base64
import importlib.util
from datetime import date, datetime
from pathlib import Path

from odoo import Command
from odoo.modules.module import get_module_path
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSedarPurchaseBid(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        request_group = cls.env.ref(
            "sedar_purchase_request.group_sedar_purchase_request_user"
        )
        officer_group = cls.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        base_group = cls.env.ref("base.group_user")
        cls.requester = cls.env["res.users"].create({
            "name": "Bid Requester",
            "login": "bid.requester@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([base_group.id, request_group.id])],
        })
        cls.officer = cls.env["res.users"].create({
            "name": "Configured Bid Officer",
            "login": "configured.bid.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([
                base_group.id, request_group.id, officer_group.id,
            ])],
        })
        cls.other_officer = cls.env["res.users"].create({
            "name": "Unconfigured Bid Officer",
            "login": "unconfigured.bid.officer@test.example",
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([
                base_group.id, request_group.id, officer_group.id,
            ])],
        })
        cls.company.sudo().sedar_procurement_inventory_officer_id = cls.officer
        cls.suppliers = cls.env["res.partner"].create([
            {"name": "Bidder One", "supplier_rank": 1},
            {"name": "Bidder Two", "supplier_rank": 1},
            {"name": "Bidder Three", "supplier_rank": 1},
        ])
        cls.products = cls.env["product.product"].create([
            {"name": "Bid Product A", "type": "consu", "is_storable": True},
            {"name": "Bid Product B", "type": "consu", "is_storable": True},
            {"name": "Bid Product C", "type": "consu", "is_storable": True},
        ])

    def _make_request(self, *, user=None, company=None, products=None):
        user = user or self.requester
        company = company or user.company_id
        products = products or self.products
        request = self.env["sedar.purchase.request"].with_user(user).create({
            "company_id": company.id,
            "required_date": datetime(2026, 9, 8, 8, 0, 0),
            "source_type": "manual",
            "justification": "Source physical goods from competing Bidders.",
            "line_ids": [
                Command.create({
                    "product_id": product.id,
                    "quantity": index + 1,
                    "estimated_unit_price": 10.0,
                })
                for index, product in enumerate(products)
            ],
        })
        request.with_user(user).action_submit()
        officer = company.sedar_procurement_inventory_officer_id
        request.with_user(officer).action_approve()
        return request

    def _make_bid(
        self, request, bidder=None, request_lines=None, prices=None, quotation=True
    ):
        bidder = bidder or self.suppliers[0]
        if request_lines is None:
            request_lines = request.line_ids
        if prices is None:
            prices = [10.0] * len(request_lines)
        values = {
            "request_id": request.id,
            "bidder_id": bidder.id,
            "received_date": date(2026, 8, 20),
            "validity_date": date(2026, 9, 20),
            "promised_delivery_date": date(2026, 9, 1),
            "line_ids": [
                Command.create({
                    "request_line_id": line.id,
                    "unit_price": price,
                })
                for line, price in zip(request_lines, prices)
            ],
        }
        if quotation:
            values.update({
                "quotation_filename": "supplier-quotation.txt",
                "quotation_file": base64.b64encode(b"private quotation"),
            })
        return self.env["sedar.purchase.bid"].with_user(self.officer).create(values)

    def _quotation_attachment(self, bid):
        return self.env["ir.attachment"].sudo().search([
            ("res_model", "=", "sedar.purchase.bid"),
            ("res_id", "=", bid.id),
            ("res_field", "=", "quotation_file"),
        ], limit=1)

    def test_subset_bids_and_currency_rounded_totals(self):
        request = self._make_request()
        lines = request.line_ids.sorted("sequence")

        first = self._make_bid(
            request, self.suppliers[0], lines[:2], [10.125, 20.125]
        )
        third = self._make_bid(
            request, self.suppliers[2], lines[2:], [30.125]
        )

        self.assertEqual(first.line_ids.request_line_id, lines[:2])
        self.assertNotIn(lines[2], first.line_ids.request_line_id)
        self.assertEqual(third.line_ids.request_line_id, lines[2:])
        self.assertEqual(first.line_ids[0].quantity, lines[0].quantity)
        self.assertEqual(first.line_ids[1].quantity, lines[1].quantity)
        self.assertEqual(first.total_amount, first.currency_id.round(50.375))
        self.assertEqual(third.total_amount, third.currency_id.round(90.375))
        self.assertEqual(request.procurement_progress, "bidding")

    def test_duplicate_header_line_and_cross_request_line_are_rejected(self):
        request = self._make_request()
        bid = self._make_bid(request, request_lines=request.line_ids[:1])

        with self.assertRaises(ValidationError):
            self._make_bid(request, self.suppliers[0], request.line_ids[1:2])
        with self.assertRaises(ValidationError):
            self.env["sedar.purchase.bid.line"].with_user(self.officer).create({
                "bid_id": bid.id,
                "request_line_id": request.line_ids[0].id,
                "unit_price": 11.0,
            })

        other_request = self._make_request(products=self.products[:1])
        with self.assertRaisesRegex(ValidationError, "another Purchase Request"):
            self.env["sedar.purchase.bid.line"].with_user(self.officer).create({
                "bid_id": bid.id,
                "request_line_id": other_request.line_ids.id,
                "unit_price": 11.0,
            })

    def test_commercial_validation_rejects_invalid_supplier_dates_quantity_and_price(self):
        request = self._make_request()
        customer = self.env["res.partner"].create({"name": "Not a Supplier"})
        with self.assertRaisesRegex(ValidationError, "eligible supplier"):
            self._make_bid(request, customer, request.line_ids[:1])
        with self.assertRaisesRegex(ValidationError, "validity"):
            self.env["sedar.purchase.bid"].with_user(self.officer).create({
                "request_id": request.id,
                "bidder_id": self.suppliers[1].id,
                "received_date": date(2026, 8, 20),
                "validity_date": date(2026, 8, 19),
            })

        bid = self._make_bid(request, self.suppliers[2], request.line_ids[:1])
        spoofed = self.env["sedar.purchase.bid.line"].with_user(self.officer).create({
            "bid_id": bid.id,
            "request_line_id": request.line_ids[1].id,
            "quantity": request.line_ids[1].quantity - 1,
            "unit_price": 1.0,
        })
        self.assertEqual(spoofed.quantity, request.line_ids[1].quantity)
        with self.assertRaisesRegex(ValidationError, "cannot be negative"):
            self.env["sedar.purchase.bid.line"].with_user(self.officer).create({
                "bid_id": bid.id,
                "request_line_id": request.line_ids[2].id,
                "unit_price": -1.0,
            })

    def test_receive_and_withdraw_preserve_immutable_history(self):
        request = self._make_request()
        bid = self._make_bid(request, request_lines=request.line_ids[:1])

        bid.with_user(self.officer).action_receive()
        self.assertEqual(bid.state, "received")
        self.assertEqual(bid.received_by_id, self.officer)
        self.assertTrue(bid.received_at)
        with self.assertRaises(AccessError):
            bid.with_user(self.officer).write({"payment_terms": "Silently changed"})
        with self.assertRaises(AccessError):
            bid.line_ids.with_user(self.officer).write({"unit_price": 99.0})
        with self.assertRaises(AccessError):
            bid.line_ids.with_user(self.officer).unlink()
        with self.assertRaises(AccessError):
            bid.with_user(self.officer).unlink()

        bid.with_user(self.officer).withdrawal_reason = "Supplier withdrew its offer."
        bid.with_user(self.officer).action_withdraw()
        self.assertEqual(bid.state, "withdrawn")
        self.assertEqual(bid.withdrawn_by_id, self.officer)
        self.assertTrue(bid.withdrawn_at)
        with self.assertRaises(AccessError):
            bid.with_user(self.officer).write({"withdrawal_reason": "Rewritten"})

    def test_receive_requires_lines_and_quotation_and_audit_cannot_be_forged(self):
        request = self._make_request()
        empty_bid = self._make_bid(
            request, self.suppliers[0], request_lines=self.env["sedar.purchase.request.line"],
            prices=[], quotation=False,
        )
        with self.assertRaisesRegex(UserError, "quoted product"):
            empty_bid.with_user(self.officer).action_receive()

        no_file = self._make_bid(
            request, self.suppliers[1], request.line_ids[:1], quotation=False,
        )
        with self.assertRaisesRegex(UserError, "Attach the supplier quotation"):
            no_file.with_user(self.officer).action_receive()
        with self.assertRaises(AccessError):
            no_file.with_user(self.officer).write({"state": "received"})
        with self.assertRaises(AccessError):
            self.env["sedar.purchase.bid"].with_user(self.officer).create({
                "request_id": request.id,
                "bidder_id": self.suppliers[2].id,
                "state": "received",
                "received_by_id": self.officer.id,
            })

    def test_exact_officer_access_blocks_requester_and_unconfigured_manager(self):
        request = self._make_request()
        bid = self._make_bid(request, request_lines=request.line_ids[:1])

        for user in (self.requester, self.other_officer):
            model = self.env["sedar.purchase.bid"].with_user(user)
            if user == self.requester:
                with self.assertRaises(AccessError):
                    model.search_read([("id", "=", bid.id)], ["total_amount"])
            else:
                self.assertFalse(model.search([("id", "=", bid.id)]))
            with self.assertRaises(AccessError):
                bid.with_user(user).read(["bidder_id", "total_amount"])
            with self.assertRaises(AccessError):
                model.create({
                    "request_id": request.id,
                    "bidder_id": self.suppliers[1].id,
                })
            with self.assertRaises(AccessError):
                bid.with_user(user).action_receive()

        with self.assertRaises(AccessError):
            request.with_user(self.requester).read(["bid_ids"])

    def test_multi_company_rules_require_the_configured_officer_for_each_company(self):
        second_company = self.env["res.company"].create({"name": "Second Bid Company"})
        officer_group = self.env.ref("sedar_marine_inventory.group_marine_inventory_manager")
        request_group = self.env.ref("sedar_purchase_request.group_sedar_purchase_request_user")
        second_officer = self.env["res.users"].create({
            "name": "Second Company Bid Officer",
            "login": "second.company.bid.officer@test.example",
            "company_id": second_company.id,
            "company_ids": [Command.set([second_company.id])],
            "group_ids": [Command.set([
                self.env.ref("base.group_user").id, request_group.id, officer_group.id,
            ])],
        })
        second_company.sudo().sedar_procurement_inventory_officer_id = second_officer
        second_request = self._make_request(
            user=second_officer, company=second_company, products=self.products[:1]
        )
        second_bid = self.env["sedar.purchase.bid"].with_user(second_officer).create({
            "request_id": second_request.id,
            "bidder_id": self.suppliers[0].id,
            "line_ids": [Command.create({
                "request_line_id": second_request.line_ids.id,
                "unit_price": 12.0,
            })],
        })

        self.officer.sudo().write({
            "company_ids": [Command.link(second_company.id)],
        })
        both_companies = self.env["sedar.purchase.bid"].with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id, second_company.id]
        )
        self.assertFalse(both_companies.search([("id", "=", second_bid.id)]))
        with self.assertRaises(AccessError):
            second_bid.with_user(self.officer).with_context(
                allowed_company_ids=[self.company.id, second_company.id]
            ).read(["total_amount"])

    def test_quotation_metadata_content_and_download_token_are_private(self):
        request = self._make_request()
        bid = self._make_bid(request, request_lines=request.line_ids[:1])
        attachment = self._quotation_attachment(bid)
        self.assertTrue(attachment)
        self.assertEqual(
            attachment.with_user(self.officer).datas,
            base64.b64encode(b"private quotation"),
        )

        for user in (self.requester, self.other_officer):
            self.assertFalse(self.env["ir.attachment"].with_user(user).search([
                ("id", "=", attachment.id),
            ]))
            with self.assertRaises(AccessError):
                attachment.with_user(user).read(["name", "datas", "mimetype"])

        with self.assertRaises(ValidationError):
            attachment.with_user(self.officer).write({"public": True})
        with self.assertRaises(ValidationError):
            attachment.with_user(self.officer).generate_access_token()

    def test_received_quotation_cannot_be_changed_deleted_or_replaced_directly(self):
        request = self._make_request()
        bid = self._make_bid(request, request_lines=request.line_ids[:1])
        bid.with_user(self.officer).action_receive()
        attachment = self._quotation_attachment(bid)

        with self.assertRaises(AccessError):
            attachment.with_user(self.officer).write({
                "datas": base64.b64encode(b"replacement quotation"),
            })
        with self.assertRaises(AccessError):
            attachment.with_user(self.officer).unlink()
        with self.assertRaises(AccessError):
            self.env["ir.attachment"].with_user(self.officer).create({
                "name": "second-quotation.txt",
                "datas": base64.b64encode(b"second quotation"),
                "res_model": "sedar.purchase.bid",
                "res_id": bid.id,
                "res_field": "quotation_file",
            })

    def test_request_baseline_is_locked_after_bid_capture(self):
        request = self._make_request()
        self._make_bid(request, request_lines=request.line_ids[:1])

        with self.assertRaises(AccessError):
            request.with_user(self.officer).write({
                "currency_id": self.env.ref("base.USD").id,
            })
        with self.assertRaises(AccessError):
            request.line_ids[:1].with_user(self.officer).write({"quantity": 99})
        with self.assertRaises(AccessError):
            self.env["sedar.purchase.request.line"].with_user(self.officer).create({
                "request_id": request.id,
                "product_id": self.products[0].id,
                "quantity": 1,
            })
        with self.assertRaises(AccessError):
            request.line_ids[:1].with_user(self.officer).unlink()
        with self.assertRaises(UserError):
            request.with_user(self.officer).action_reject()

    def test_legacy_bid_migration_is_narrow_and_idempotent(self):
        eligible = self._make_request(products=self.products[:2])
        eligible.sudo().vendor_id = self.suppliers[0]
        ordered = self._make_request(products=self.products[:1])
        ordered.sudo().vendor_id = self.suppliers[1]
        self.env["purchase.order"].sudo().create({
            "partner_id": self.suppliers[1].id,
            "company_id": self.company.id,
            "sedar_purchase_request_id": ordered.id,
        })
        self.env.flush_all()

        migration_path = (
            Path(get_module_path("sedar_purchase_request"))
            / "migrations/19.0.3.0.0/post-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_purchase_bid_post_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        migration.migrate(self.env.cr, "19.0.2.0.0")
        migration.migrate(self.env.cr, "19.0.2.0.0")

        eligible_bids = self.env["sedar.purchase.bid"].sudo().search([
            ("request_id", "=", eligible.id),
        ])
        self.assertEqual(len(eligible_bids), 1)
        self.assertEqual(eligible_bids.state, "received")
        self.assertEqual(eligible_bids.capture_source, "legacy")
        self.assertFalse(eligible_bids.quotation_file)
        self.assertEqual(eligible_bids.line_ids.request_line_id, eligible.line_ids)
        self.assertFalse(self.env["sedar.purchase.bid"].sudo().search([
            ("request_id", "=", ordered.id),
        ]))

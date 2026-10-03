import base64
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


LOW_STOCK_TYPE = "sedar_purchase_request.mail_activity_type_low_stock"
PR_FORM = "sedar_purchase_request.report_purchase_request_form"
ABSTRACT = "sedar_purchase_request.report_abstract_of_bids"


@tagged("post_install", "-at_install")
class TestSedarProcurementAlertAndForms(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        base_group = cls.env.ref("base.group_user")
        request_group = cls.env.ref("sedar_purchase_request.group_sedar_purchase_request_user")
        officer_group = cls.env.ref("sedar_marine_inventory.group_marine_inventory_manager")
        cls.requester = cls.env["res.users"].create({
            "name": "Forms Requester", "login": "forms.requester@test.example",
            "company_id": cls.company.id, "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([base_group.id, request_group.id])],
        })
        cls.officer = cls.env["res.users"].create({
            "name": "Forms Officer", "login": "forms.officer@test.example",
            "company_id": cls.company.id, "company_ids": [Command.set([cls.company.id])],
            "group_ids": [Command.set([base_group.id, request_group.id, officer_group.id])],
        })
        cls.company.sudo().sedar_procurement_inventory_officer_id = cls.officer
        warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock_location = warehouse.lot_stock_id
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.rope = cls._make_item("Forms Test Rope", "FORMS-ROPE", reorder_point=10)
        cls.env["stock.quant"]._update_available_quantity(cls.rope, cls.stock_location, 50)

    @classmethod
    def _make_item(cls, name, code, reorder_point=0.0, inventory_item=True):
        return cls.env["product.product"].create({
            "name": name, "default_code": code, "type": "consu", "is_storable": True,
            "sedar_inventory_item": inventory_item, "sedar_reorder_point": reorder_point,
            "supplier_taxes_id": [Command.clear()],
        })

    def _move(self, product, qty, source, destination):
        move = self.env["stock.move"].create({
            "product_id": product.id, "product_uom_qty": qty,
            "product_uom": product.uom_id.id, "location_id": source.id,
            "location_dest_id": destination.id, "company_id": self.company.id,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = qty
        move.picked = True
        move._action_done()

    def _issue(self, product, qty):
        self._move(product, qty, self.stock_location, self.customer_location)

    def _receive(self, product, qty):
        self._move(product, qty, self.supplier_location, self.stock_location)

    def _alerts(self, product):
        return self.env["mail.activity"].search([
            ("res_model", "=", "product.product"), ("res_id", "=", product.id),
            ("activity_type_id", "=", self.env.ref(LOW_STOCK_TYPE).id),
        ])

    def test_stock_move_dropping_to_reorder_point_alerts_only_the_officer_once(self):
        self._issue(self.rope, 5)
        self.assertFalse(self._alerts(self.rope))

        self._issue(self.rope, 40)
        alerts = self._alerts(self.rope)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.user_id, self.officer)
        self.assertIn("Low stock", alerts.summary)

        self._issue(self.rope, 2)
        self.assertEqual(len(self._alerts(self.rope)), 1)

    def test_alert_closes_when_stock_recovers_and_reports_out_of_stock(self):
        self._issue(self.rope, 45)
        self._issue(self.rope, 5)
        self.assertEqual(len(self._alerts(self.rope)), 1)
        self._receive(self.rope, 100)
        self.assertFalse(self._alerts(self.rope))

        self._issue(self.rope, 100)
        self._issue(self.rope, 50)
        self.assertIn("Out of stock", self._alerts(self.rope).summary)

    def test_no_alert_without_officer_or_for_non_inventory_items(self):
        plain = self._make_item("Forms Plain Product", "FORMS-PLAIN", 10, inventory_item=False)
        self.env["stock.quant"]._update_available_quantity(plain, self.stock_location, 50)
        self._issue(plain, 45)
        self.assertFalse(self._alerts(plain))

        self.company.sudo().sedar_procurement_inventory_officer_id = False
        self._issue(self.rope, 45)
        self.assertFalse(self._alerts(self.rope))

    def _make_request(self):
        products = self.rope | self._make_item("Forms Test Shackle", "FORMS-SHACKLE")
        request = self.env["sedar.purchase.request"].with_user(self.requester).create({
            "required_date": datetime.combine(fields.Date.today() + timedelta(days=30), datetime.min.time()),
            "source_type": "inventory",
            "justification": "Restock rope before the next assist.",
            "line_ids": [
                Command.create({"product_id": product.id, "quantity": 10 * (index + 1), "estimated_unit_price": 25.0})
                for index, product in enumerate(products)
            ],
        })
        request.with_user(self.requester).action_submit()
        request.with_user(self.officer).action_approve()
        return request

    def _make_bid(self, request, supplier, request_line, price):
        bid = self.env["sedar.purchase.bid"].with_user(self.officer).create({
            "request_id": request.id,
            "bidder_id": supplier.id,
            "received_date": fields.Date.today(),
            "validity_date": fields.Date.today() + timedelta(days=30),
            "promised_delivery_date": fields.Date.today() + timedelta(days=10),
            "quotation_filename": "forms-quotation.txt",
            "quotation_file": base64.b64encode(b"forms quotation"),
            "line_ids": [Command.create({"request_line_id": request_line.id, "unit_price": price})],
        })
        bid.with_user(self.officer).action_receive()
        return bid

    def _html(self, report_ref, records, user=None):
        records = records.with_user(user) if user else records
        return self.env["ir.actions.report"].with_user(records.env.user)._render_qweb_html(
            report_ref, records.ids
        )[0].decode()

    def test_purchase_request_form_shows_lines_totals_and_approval(self):
        request = self._make_request()
        html = self._html(PR_FORM, request, self.requester)
        self.assertIn(request.name, html)
        self.assertIn("Forms Test Rope", html)
        self.assertIn("Forms Test Shackle", html)
        self.assertIn("Restock rope before the next assist.", html)
        self.assertIn("Forms Requester", html)
        self.assertIn("Forms Officer", html)

    def test_abstract_of_bids_marks_award_reason_and_unquoted_items(self):
        request = self._make_request()
        rope_line = request.line_ids.filtered(lambda line: line.product_id == self.rope)
        supplier_a, supplier_b = self.env["res.partner"].create([
            {"name": "Abstract Bidder A", "supplier_rank": 1},
            {"name": "Abstract Bidder B", "supplier_rank": 1},
        ])
        self._make_bid(request, supplier_a, rope_line, 30.0)
        winner = self._make_bid(request, supplier_b, rope_line, 28.0)
        rope_line.with_user(self.officer)._create_line_award(
            winner.line_ids, "Cheaper and delivers sooner."
        )
        html = self._html(ABSTRACT, request, self.officer)
        self.assertIn("Abstract Bidder A", html)
        self.assertIn("Abstract Bidder B", html)
        self.assertIn("AWARDED", html)
        self.assertIn("Cheaper and delivers sooner.", html)
        self.assertIn("No bids received for this item.", html)

    def test_abstract_of_bids_is_officer_only(self):
        request = self._make_request()
        with self.assertRaises(AccessError):
            self._html(ABSTRACT, request, self.requester)

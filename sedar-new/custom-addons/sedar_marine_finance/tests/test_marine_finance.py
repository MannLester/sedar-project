from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestMarineFinanceWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        cls.manager = new_test_user(
            cls.env,
            login="sedar_finance_test_manager",
            groups="sedar_marine_finance.group_accounting_manager",
        )
        cls.billing = new_test_user(
            cls.env,
            login="sedar_finance_test_billing",
            groups="sedar_marine_finance.group_billing_officer",
        )
        cls.client = cls.env["res.partner"].create({
            "name": "Finance Test Client",
            "is_company": True,
        })
        cls.port = cls.env["sedar.marine.port"].create({
            "name": "Finance Test Port",
            "code": "FIN-PORT",
        })
        cls.terminal = cls.env["sedar.marine.berth"].create({
            "name": "Finance Test Terminal",
            "code": "FIN-TERM",
            "port_id": cls.port.id,
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({
            "name": "Finance Test Tug",
            "minimum_bollard_pull": 20,
        })
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Finance Test Towage",
            "code": "FIN-TOW",
            "pricing_basis": "per_tug_hour",
            "standard_rate": 0,
            "currency_id": cls.currency.id,
        })
        cls.tariff = cls.env["sedar.client.tariff"].with_user(cls.manager).create({
            "partner_id": cls.client.id,
            "service_type_id": cls.service.id,
            "port_id": cls.port.id,
            "terminal_id": cls.terminal.id,
            "tug_class_id": cls.tug_class.id,
            "pricing_basis": "per_tug_hour",
            "rate": 1000,
            "minimum_charge": 2000,
            "currency_id": cls.currency.id,
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "approval_reference": "TEST-AUTHORIZATION",
        })
        cls.tariff.with_user(cls.manager).action_approve()

    def _make_order(self, *, service=None, tug_count=2, state="in_progress"):
        service = service or self.service
        start = datetime(2026, 8, 4, 8, 0, 0)
        order = self.env["sedar.marine.service.order"].create({
            "client_id": self.client.id,
            "assisted_vessel_name": "MV Finance Test",
            "service_type_id": service.id,
            "number_of_tugs": tug_count,
            "tug_class_id": self.tug_class.id,
            "scope_of_work": "Finance workflow test.",
            "port_id": self.port.id,
            "terminal_id": self.terminal.id,
            "requested_start": start,
            "estimated_duration_hours": 2,
            "state": "quoted",
        })
        order.action_confirm()
        order.state = state
        return order

    def _add_completed_tug(self, order, code, start, end):
        tug = self.env["sedar.tugboat"].create({
            "name": "Test Tug %s" % code,
            "registration_number": "FIN-TUG-%s" % code,
            "tug_class_id": self.tug_class.id,
        })
        return self.env["sedar.tug.assignment"].sudo().create({
            "order_id": order.id,
            "tugboat_id": tug.id,
            "state": "confirmed",
            "actual_start": start,
            "actual_end": end,
            "completion_note": "Completed by Tug Master.",
            "completion_state": "submitted",
        })

    def _add_completed_operation(self, order):
        start = fields.Datetime.to_datetime(order.requested_start)
        return self.env["sedar.marine.operation"].create({
            "order_id": order.id,
            "state": "completed",
            "actual_start": start,
            "actual_end": start + timedelta(hours=3),
            "completion_summary": "Automated test operation completed.",
        })

    def test_multi_tug_actual_time_to_draft_invoice(self):
        order = self._make_order()
        start = fields.Datetime.to_datetime(order.requested_start)
        self._add_completed_tug(order, "A", start, start + timedelta(hours=2))
        self._add_completed_tug(order, "B", start, start + timedelta(hours=3))
        order._sync_completion_from_tugs()

        self.assertEqual(order.state, "completed")
        self.assertEqual(order.billing_status, "not_ready")
        self._add_completed_operation(order)

        self.assertTrue(order.automated_completion_handoff)
        self.assertEqual(order.billing_status, "review")
        self.assertEqual(order.actual_billable_quantity, 5)
        self.assertEqual(order.base_billable_amount, 5000)

        self.env["sedar.marine.billing.adjustment"].with_user(self.billing).create({
            "order_id": order.id,
            "description": "Documented standby",
            "quantity": 1,
            "unit_rate": 500,
            "reason": "Finance test adjustment",
        })
        self.assertEqual(order.total_billable_amount, 5500)

        order.with_user(self.billing).action_mark_billing_reviewed()
        order.with_user(self.billing).action_create_draft_invoice()
        invoice = order.invoice_ids
        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.amount_total, 5500)
        self.assertEqual(order.billing_status, "draft_invoice")
        with self.assertRaises(UserError):
            order.with_user(self.billing).action_create_draft_invoice()

    def test_missing_tariff_is_pricing_exception(self):
        service = self.env["sedar.marine.service.type"].create({
            "name": "Unpriced Emergency Service",
            "code": "FIN-NO-TARIFF",
            "pricing_basis": "per_service",
            "standard_rate": 999999,
            "currency_id": self.currency.id,
        })
        order = self._make_order(service=service, tug_count=1, state="completed")
        start = fields.Datetime.to_datetime(order.requested_start)
        self._add_completed_tug(order, "NO-TARIFF", start, start + timedelta(hours=2))
        self._add_completed_operation(order)
        self.assertFalse(order.confirmed_tariff_id)
        self.assertEqual(order.billing_status, "pricing_exception")

    def test_tariff_is_manager_controlled_and_immutable(self):
        with self.assertRaises(AccessError):
            self.env["sedar.client.tariff"].with_user(self.billing).create({
                "partner_id": self.client.id,
                "service_type_id": self.service.id,
                "port_id": self.port.id,
                "terminal_id": self.terminal.id,
                "pricing_basis": "per_service",
                "rate": 1,
                "currency_id": self.currency.id,
                "valid_from": "2027-01-01",
            })
        with self.assertRaises(UserError):
            self.tariff.with_user(self.manager).write({"rate": 1200})

    def test_finance_can_return_completion_but_not_rewrite_it(self):
        order = self._make_order(tug_count=1)
        start = fields.Datetime.to_datetime(order.requested_start)
        assignment = self._add_completed_tug(order, "RETURN", start, start + timedelta(hours=2))
        order._sync_completion_from_tugs()
        operation = self._add_completed_operation(order)
        self.assertEqual(order.billing_status, "review")
        assignment.with_user(self.billing).completion_return_reason = "Incorrect actual end time."
        assignment.with_user(self.billing).action_return_completion()
        self.assertEqual(assignment.completion_state, "returned")
        self.assertEqual(order.state, "in_progress")
        self.assertEqual(operation.state, "in_progress")
        self.assertFalse(operation.actual_end)
        self.assertFalse(order.automated_completion_handoff)
        self.assertEqual(order.billing_status, "not_ready")
        with self.assertRaises(AccessError):
            assignment.with_user(self.billing).write({"actual_end": start + timedelta(hours=4)})

    def test_operation_completion_alone_does_not_enter_billing(self):
        order = self._make_order(tug_count=2, state="completed")
        self._add_completed_operation(order)
        self.assertFalse(order.automated_completion_handoff)
        self.assertEqual(order.billing_status, "not_ready")

    def test_all_tugs_without_completed_operation_do_not_enter_billing(self):
        order = self._make_order(tug_count=2)
        start = fields.Datetime.to_datetime(order.requested_start)
        self._add_completed_tug(order, "HANDOFF-A", start, start + timedelta(hours=2))
        self._add_completed_tug(order, "HANDOFF-B", start, start + timedelta(hours=2))
        order._sync_completion_from_tugs()
        self.assertEqual(order.state, "completed")
        self.assertFalse(order.automated_completion_handoff)
        self.assertEqual(order.billing_status, "not_ready")

    def test_return_after_review_clears_review_and_reopens_operation(self):
        order = self._make_order(tug_count=1)
        start = fields.Datetime.to_datetime(order.requested_start)
        assignment = self._add_completed_tug(order, "REVIEW-RETURN", start, start + timedelta(hours=2))
        order._sync_completion_from_tugs()
        operation = self._add_completed_operation(order)
        order.with_user(self.billing).action_mark_billing_reviewed()
        self.assertTrue(order.billing_reviewed_at)

        assignment.with_user(self.billing).completion_return_reason = "Tug Master must correct time."
        assignment.with_user(self.billing).action_return_completion()

        self.assertFalse(order.billing_reviewed_at)
        self.assertEqual(order.billing_status, "not_ready")
        self.assertEqual(operation.state, "in_progress")

    def test_active_invoice_blocks_return_but_cancelled_draft_allows_it(self):
        order = self._make_order(tug_count=1)
        start = fields.Datetime.to_datetime(order.requested_start)
        assignment = self._add_completed_tug(order, "INVOICE-RETURN", start, start + timedelta(hours=2))
        order._sync_completion_from_tugs()
        self._add_completed_operation(order)
        order.with_user(self.billing).action_mark_billing_reviewed()
        order.with_user(self.billing).action_create_draft_invoice()

        assignment.with_user(self.billing).completion_return_reason = "Correct actual service time."
        with self.assertRaises(UserError):
            assignment.with_user(self.billing).action_return_completion()

        order.invoice_ids.with_user(self.manager).button_cancel()
        assignment.with_user(self.billing).action_return_completion()
        self.assertEqual(assignment.completion_state, "returned")
        self.assertEqual(order.billing_status, "not_ready")

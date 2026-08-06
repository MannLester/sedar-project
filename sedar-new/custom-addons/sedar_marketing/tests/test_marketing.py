from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from odoo.addons.sedar_marketing.hooks import ensure_marketing_demo


class TestSedarMarketing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.officer = cls.env["res.users"].create({
            "name": "Marketing Test Officer",
            "login": "sedar-marketing-test-officer",
            "email": "marketing-test@example.test",
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_marketing.group_marketing_officer").id,
            ])],
        })
        cls.manager = cls.env["res.users"].create({
            "name": "Marketing Test Manager",
            "login": "sedar-marketing-test-manager",
            "email": "marketing-manager-test@example.test",
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_marketing.group_marketing_manager").id,
            ])],
        })
        cls.customer = cls.env["res.partner"].create({
            "name": "Marketing Test Shipping",
            "is_company": True,
            "sedar_is_customer_account": True,
            "sedar_customer_type": "shipping_company",
            "sedar_account_status": "active",
            "sedar_assigned_marketing_user_id": cls.officer.id,
        })
        cls.contact = cls.env["res.partner"].create({
            "name": "Marina Contact",
            "parent_id": cls.customer.id,
            "email": "marina@example.test",
            "sedar_can_approve_quotations": True,
            "sedar_can_sign_contracts": True,
            "sedar_can_coordinate_operations": True,
        })
        cls.customer.sedar_primary_contact_id = cls.contact
        cls.service_type = cls.env.ref("sedar_marine_operations.service_type_harbor")
        cls.port = cls.env.ref("sedar_marine_operations.port_batangas")
        cls.order = cls.env["sedar.marine.service.order"].with_user(cls.officer).create({
            "client_id": cls.customer.id,
            "contact_id": cls.contact.id,
            "request_channel": "email",
            "assisted_vessel_name": "MV Marketing Test",
            "service_type_id": cls.service_type.id,
            "scope_of_work": "Harbor assistance",
            "port_id": cls.port.id,
            "requested_start": fields.Datetime.now() + timedelta(days=7),
            "estimated_duration_hours": 2,
        })

    def test_service_request_and_quotation_workflow(self):
        order = self.order.with_user(self.officer)
        order.action_marketing_submit_review()
        order.action_marketing_send_operations()
        order.action_marketing_prepare_quotation()
        quotation = self.env["sedar.marketing.quotation"].with_user(self.officer).create({
            "service_order_id": order.id,
            "customer_id": self.customer.id,
            "contact_id": self.contact.id,
            "subject": "Harbor assistance quotation",
            "line_ids": [Command.create({
                "description": "Harbor assistance", "quantity": 2,
                "unit_price": 10000, "tax_rate": 12,
            })],
        })
        self.assertEqual(quotation.amount_total, 22400)
        quotation.action_submit_internal_approval()
        quotation.with_user(self.manager).action_approve_internal()
        quotation.action_send()
        self.assertEqual(order.marketing_status, "awaiting_customer")
        quotation.action_record_customer_approval()
        self.assertEqual(quotation.status, "customer_approved")
        self.assertEqual(order.marketing_status, "approved")
        self.assertEqual(order.state, "confirmed")
        self.assertTrue(self.env["sedar.marketing.transaction"].search([
            ("source_model", "=", quotation._name), ("source_record_id", "=", quotation.id)
        ]))

    def test_contract_requires_verified_signatures(self):
        quotation = self.env["sedar.marketing.quotation"].create({
            "service_order_id": self.order.id, "customer_id": self.customer.id,
            "contact_id": self.contact.id, "subject": "Approved quotation",
            "status": "customer_approved",
            "line_ids": [Command.create({"description": "Service", "quantity": 1, "unit_price": 50000})],
        })
        contract = self.env["sedar.marketing.contract"].create({
            "title": "Harbor Service Contract", "customer_id": self.customer.id,
            "contact_id": self.contact.id, "quotation_id": quotation.id,
            "service_order_id": self.order.id, "service_type_id": self.service_type.id,
            "vessel_name": self.order.assisted_vessel_name,
            "effective_date": fields.Date.today() + timedelta(days=1),
            "expiration_date": fields.Date.today() + timedelta(days=366),
            "contract_value": quotation.amount_total,
            "selected_customer_contact_id": self.contact.id,
        })
        contract.action_submit_internal_review()
        contract.with_user(self.manager).action_approve_internal_review()
        contract.action_send_for_signature()
        with self.assertRaises(UserError):
            contract.action_activate()
        signature_model = self.env["sedar.marketing.contract.signature"]
        for party, name in (("sedar", "SEDAR Signatory"), ("customer", self.contact.name)):
            signature_model.create({
                "contract_id": contract.id, "party": party, "signatory_name": name,
                "organization": "SEDAR" if party == "sedar" else self.customer.name,
                "verification_status": "verified",
            })
        self.assertEqual(contract.signature_status, "fully_executed")
        contract.action_activate()
        self.assertEqual(contract.status, "active")

    def test_document_ownership_and_append_only_audit(self):
        marketing_document = self.env["sedar.marketing.document"].with_user(self.officer).create({
            "customer_id": self.customer.id, "title": "Marketing capability brief",
            "document_type": "marketing_material", "department": "marketing",
            "source": "uploaded",
        })
        self.env["sedar.marketing.document.version"].with_user(self.officer).create({
            "document_id": marketing_document.id, "filename": "brief.pdf",
            "mime_type": "application/pdf", "size_bytes": 1024,
        })
        self.assertEqual(marketing_document.current_version, 1)
        official = self.env["sedar.marketing.document"].sudo().with_context(
            sedar_official_document_sync=True
        ).create({
            "customer_id": self.customer.id, "title": "Official service report",
            "document_type": "service_report", "department": "operations", "source": "official",
        })
        with self.assertRaises(AccessError):
            self.env["sedar.marketing.document"].with_user(self.officer).browse(official.id).write({"title": "Changed"})
        activity = self.env["sedar.marketing.activity"].log(
            self.customer, "system", "updated", "Restricted value changed.",
            changes=[("api_token", "old-secret", "new-secret")], visibility="restricted",
        )
        self.assertIn("Restricted field updated", activity.change_summary)
        self.assertNotIn("new-secret", activity.change_summary)
        with self.assertRaises(AccessError):
            activity.write({"description": "Changed"})

    def test_appointment_status_history(self):
        start = fields.Datetime.now() + timedelta(days=2)
        appointment = self.env["calendar.event"].with_user(self.officer).create({
            "name": "Customer coordination",
            "start": start, "stop": start + timedelta(hours=1),
            "sedar_is_marketing_appointment": True,
            "sedar_customer_id": self.customer.id,
            "sedar_contact_id": self.contact.id,
            "sedar_appointment_type": "service_consultation",
            "sedar_appointment_status": "scheduled",
        })
        appointment.action_sedar_confirm()
        appointment.sedar_outcome = "Scope confirmed"
        appointment.action_sedar_complete()
        self.assertEqual(appointment.sedar_appointment_status, "completed")
        self.assertGreaterEqual(len(appointment.sedar_status_history_ids), 3)

    def test_noop_reconciliation_does_not_pollute_activity_log(self):
        activity_model = self.env["sedar.marketing.activity"]
        domain = [("related_model", "=", self.order._name), ("related_record_id", "=", self.order.id)]
        before_order = activity_model.search_count(domain)
        self.order.write({
            "state": self.order.state,
            "service_type_id": self.order.service_type_id.id,
            "assisted_vessel_name": self.order.assisted_vessel_name,
            "requested_start": self.order.requested_start,
        })
        self.assertEqual(activity_model.search_count(domain), before_order)

        partner_domain = [("related_model", "=", self.customer._name), ("related_record_id", "=", self.customer.id)]
        before_partner = activity_model.search_count(partner_domain)
        self.customer.write({
            "name": self.customer.name,
            "sedar_account_status": self.customer.sedar_account_status,
            "sedar_assigned_marketing_user_id": self.customer.sedar_assigned_marketing_user_id.id,
        })
        self.assertEqual(activity_model.search_count(partner_domain), before_partner)

    def test_workspace_reconciliation_is_repeatable(self):
        company = self.env.company
        dashboard_model = self.env["sedar.marketing.dashboard"]
        transaction_model = self.env["sedar.marketing.transaction"]

        company.sedar_ensure_marketing_workspace()
        customer_code = self.customer.sedar_customer_code
        dashboard_count = dashboard_model.search_count([("company_id", "=", company.id)])
        transaction_count = transaction_model.search_count([])

        company.sedar_ensure_marketing_workspace()

        self.assertTrue(customer_code)
        self.assertEqual(self.customer.sedar_customer_code, customer_code)
        self.assertEqual(
            dashboard_model.search_count([("company_id", "=", company.id)]),
            dashboard_count,
        )
        self.assertEqual(transaction_model.search_count([]), transaction_count)
        self.assertIn(
            self.env.ref("sedar_marketing.group_marketing_manager"),
            self.env.ref("base.user_admin").group_ids,
        )

    def test_marketing_demo_reconciliation_is_repeatable(self):
        self.assertTrue(ensure_marketing_demo(self.env))
        models = {
            "sedar.marketing.quotation": self.env["sedar.marketing.quotation"].search_count([]),
            "sedar.marketing.contract": self.env["sedar.marketing.contract"].search_count([]),
            "calendar.event": self.env["calendar.event"].search_count([
                ("sedar_is_marketing_appointment", "=", True),
            ]),
            "sedar.marketing.document": self.env["sedar.marketing.document"].search_count([]),
            "sedar.marketing.document.request": self.env["sedar.marketing.document.request"].search_count([]),
            "sedar.marketing.internal.note": self.env["sedar.marketing.internal.note"].search_count([]),
        }

        self.assertTrue(ensure_marketing_demo(self.env))

        self.assertEqual(self.env["sedar.marketing.quotation"].search_count([]), models["sedar.marketing.quotation"])
        self.assertEqual(self.env["sedar.marketing.contract"].search_count([]), models["sedar.marketing.contract"])
        self.assertEqual(self.env["calendar.event"].search_count([
            ("sedar_is_marketing_appointment", "=", True),
        ]), models["calendar.event"])
        self.assertEqual(self.env["sedar.marketing.document"].search_count([]), models["sedar.marketing.document"])
        self.assertEqual(self.env["sedar.marketing.document.request"].search_count([]), models["sedar.marketing.document.request"])
        self.assertEqual(self.env["sedar.marketing.internal.note"].search_count([]), models["sedar.marketing.internal.note"])
        self.assertEqual(
            self.env.ref("sedar_marketing.demo_contract_active").signature_status,
            "fully_executed",
        )

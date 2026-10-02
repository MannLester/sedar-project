from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.sedar_marine_dispatch.controllers import portal as dispatch_portal_controller
from odoo.addons.sedar_marine_dispatch.controllers.portal import SedarMarineDispatchPortal
from odoo.addons.sedar_marine_operations.controllers import portal as operations_portal_controller
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDispatchPortalCompanyIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Dispatch Portal Other Company"})
        cls.client = cls.env["res.partner"].create({"name": "Shared Dispatch Portal Client"})
        contact = cls.env["res.partner"].create({
            "name": "Dispatch Portal Contact",
            "parent_id": cls.client.id,
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Dispatch Company A Portal User",
            "login": "dispatch-company-a-portal@example.com",
            "partner_id": contact.id,
            "company_id": cls.company_a.id,
            "company_ids": [Command.set([cls.company_a.id])],
            "group_ids": [Command.set([cls.env.ref("base.group_portal").id])],
        })
        service = cls.env["sedar.marine.service.type"].create({
            "name": "Dispatch Portal Company Service",
            "code": "DISPATCH-PORTAL-COMPANY",
            "pricing_basis": "per_service",
        })
        port = cls.env["sedar.marine.port"].create({
            "name": "Dispatch Portal Company Port",
            "code": "DISPATCH-PORTAL-COMPANY",
        })
        cls.order_a = cls._create_order(cls.company_a, service, port, contact, "A")
        cls.order_b = cls._create_order(cls.company_b, service, port, contact, "B")
        cls.operation_a = cls.env["sedar.marine.operation"].sudo().create({
            "order_id": cls.order_a.id,
        })
        cls.operation_b = cls.env["sedar.marine.operation"].sudo().create({
            "order_id": cls.order_b.id,
        })

    @classmethod
    def _create_order(cls, company, service, port, contact, suffix):
        return cls.env["sedar.marine.service.order"].sudo().with_company(company).create({
            "company_id": company.id,
            "client_id": cls.client.id,
            "contact_id": contact.id,
            "assisted_vessel_name": f"MV Dispatch Portal {suffix}",
            "service_type_id": service.id,
            "scope_of_work": "Verify dispatch portal company isolation.",
            "port_id": port.id,
            "requested_start": fields.Datetime.now(),
        })

    def test_sudo_operation_domain_limits_shared_client_to_allowed_companies(self):
        portal_env = self.env["res.users"].with_user(self.portal_user).env
        fake_request = SimpleNamespace(env=portal_env)
        controller = SedarMarineDispatchPortal()

        with (
            patch.object(operations_portal_controller, "request", fake_request),
            patch.object(dispatch_portal_controller, "request", fake_request),
        ):
            self.assertEqual(controller._get_portal_order(self.order_a.id), self.order_a)
            self.assertFalse(controller._get_portal_order(self.order_b.id))
            visible = self.env["sedar.marine.operation"].sudo().search(
                controller._operation_domain(self.order_a)
            )
            self.assertEqual(visible, self.operation_a)
            self.assertEqual(
                controller._client_log_domain(self.operation_a),
                [
                    ("operation_id", "=", self.operation_a.id),
                    ("company_id", "in", self.company_a.ids),
                    ("client_visible", "=", True),
                ],
            )
            self.assertEqual(
                controller._client_delay_domain(self.operation_a),
                [
                    ("operation_id", "=", self.operation_a.id),
                    ("company_id", "in", self.company_a.ids),
                    ("client_visible", "=", True),
                ],
            )

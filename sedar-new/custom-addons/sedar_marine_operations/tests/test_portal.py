from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.sedar_marine_operations.controllers.portal import (
    SedarMarineCustomerPortal,
)
from odoo.addons.sedar_marine_operations.controllers import portal as portal_controller
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPortalOrderValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Portal Other Company"})
        cls.client = cls.env["res.partner"].create({"name": "Shared Portal Client"})
        cls.portal_partner = cls.env["res.partner"].create({
            "name": "Shared Client Portal Contact",
            "parent_id": cls.client.id,
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Company A Portal User",
            "login": "company-a-portal@example.com",
            "partner_id": cls.portal_partner.id,
            "company_id": cls.company_a.id,
            "company_ids": [Command.set([cls.company_a.id])],
            "group_ids": [Command.set([cls.env.ref("base.group_portal").id])],
        })
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Portal Company Test Service",
            "code": "PORTAL-COMPANY",
            "pricing_basis": "per_service",
        })
        cls.port = cls.env["sedar.marine.port"].create({
            "name": "Portal Company Test Port",
            "code": "PORTAL-COMPANY",
        })
        cls.order_a = cls._create_order(cls.company_a, "A")
        cls.order_b = cls._create_order(cls.company_b, "B")

    @classmethod
    def _create_order(cls, company, suffix):
        return cls.env["sedar.marine.service.order"].sudo().with_company(company).create({
            "company_id": company.id,
            "client_id": cls.client.id,
            "contact_id": cls.portal_partner.id,
            "assisted_vessel_name": f"MV Portal Company {suffix}",
            "service_type_id": cls.service.id,
            "scope_of_work": "Verify portal company isolation.",
            "port_id": cls.port.id,
            "requested_start": fields.Datetime.now(),
        })

    def _portal_request(self):
        portal_env = self.env["res.users"].with_user(self.portal_user).env
        return patch.object(portal_controller, "request", SimpleNamespace(env=portal_env))

    def test_requested_start_with_missing_port_returns_validation_failure(self):
        controller = SedarMarineCustomerPortal()
        missing_port = self.env["sedar.marine.port"]

        self.assertFalse(
            controller._parse_requested_start("2026-08-23T09:00", missing_port)
        )

    def test_sudo_order_domain_still_limits_shared_client_to_allowed_companies(self):
        controller = SedarMarineCustomerPortal()

        with self._portal_request():
            visible = self.env["sedar.marine.service.order"].sudo().search(
                controller._order_domain()
            )
            self.assertEqual(visible, self.order_a)
            self.assertEqual(controller._get_portal_order(self.order_a.id), self.order_a)
            self.assertFalse(controller._get_portal_order(self.order_b.id))
            self.assertEqual(controller._order_count(), 1)

    def test_portal_home_visibility_ignores_orders_from_disabled_companies(self):
        controller = SedarMarineCustomerPortal()

        with self._portal_request(), patch.object(
            CustomerPortal,
            "_prepare_portal_layout_values",
            return_value={},
        ):
            values = controller._prepare_portal_layout_values()

        self.assertTrue(values["sedar_has_orders"])

        self.order_a.unlink()
        with self._portal_request(), patch.object(
            CustomerPortal,
            "_prepare_portal_layout_values",
            return_value={},
        ):
            values = controller._prepare_portal_layout_values()

        self.assertFalse(values["sedar_has_orders"])

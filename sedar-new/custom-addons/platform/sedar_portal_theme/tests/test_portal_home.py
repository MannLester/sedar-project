from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.sedar_portal_theme.controllers import portal as portal_controller
from odoo.addons.sedar_portal_theme.controllers.portal import SedarPortalHome
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPortalHomeCompanyScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Portal Theme Other Company"})
        cls.client = cls.env["res.partner"].create({"name": "Portal Theme Shared Client"})
        cls.contact = cls.env["res.partner"].create({
            "name": "Portal Theme Contact",
            "parent_id": cls.client.id,
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal Theme Company A User",
            "login": "portal-theme-company-a@example.com",
            "partner_id": cls.contact.id,
            "company_id": cls.company_a.id,
            "company_ids": [Command.set([cls.company_a.id])],
            "group_ids": [Command.set([cls.env.ref("base.group_portal").id])],
        })
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Portal Theme Company Service",
            "code": "PORTAL-THEME-COMPANY",
            "pricing_basis": "per_service",
        })
        cls.port = cls.env["sedar.marine.port"].create({
            "name": "Portal Theme Company Port",
            "code": "PORTAL-THEME-COMPANY",
        })

    @classmethod
    def _create_order(cls, company, suffix):
        return cls.env["sedar.marine.service.order"].sudo().with_company(company).create({
            "company_id": company.id,
            "client_id": cls.client.id,
            "contact_id": cls.contact.id,
            "assisted_vessel_name": f"MV Portal Theme {suffix}",
            "service_type_id": cls.service.id,
            "scope_of_work": "Verify portal home company isolation.",
            "port_id": cls.port.id,
            "requested_start": fields.Datetime.now(),
        })

    def _request(self):
        portal_env = self.env["res.users"].with_user(self.portal_user).env
        return patch.object(
            portal_controller,
            "request",
            SimpleNamespace(env=portal_env, redirect=lambda target: target),
        )

    def test_disabled_company_order_does_not_redirect_portal_home(self):
        self._create_order(self.company_b, "B")
        controller = SedarPortalHome()

        with self._request(), patch.object(CustomerPortal, "home", return_value="default"):
            self.assertEqual(SedarPortalHome.home.original_endpoint(controller), "default")

        self._create_order(self.company_a, "A")
        with self._request(), patch.object(CustomerPortal, "home", return_value="default"):
            self.assertEqual(
                SedarPortalHome.home.original_endpoint(controller),
                "/my/sedar/orders",
            )

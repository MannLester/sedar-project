from odoo.addons.sedar_marine_operations.controllers.portal import (
    SedarMarineCustomerPortal,
)
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPortalOrderValidation(TransactionCase):
    def test_requested_start_with_missing_port_returns_validation_failure(self):
        controller = SedarMarineCustomerPortal()
        missing_port = self.env["sedar.marine.port"]

        self.assertFalse(
            controller._parse_requested_start("2026-08-23T09:00", missing_port)
        )

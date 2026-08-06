from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSedarAisDemo(TransactionCase):
    def test_dashboard_payload_exposes_simulation_and_crew(self):
        self.env.company.sedar_ensure_ais_demo()
        payload = self.env["sedar.ais.position"].get_dashboard_data()
        self.assertTrue(payload["simulation"])
        self.assertTrue(payload["fleet"])
        self.assertTrue(all("crew" in tug and "status" in tug for tug in payload["fleet"]))

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

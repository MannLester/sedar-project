from odoo.tests.common import TransactionCase


class TestVessel(TransactionCase):

    def test_create_vessel(self):
        vessel = self.env['sedar.vessel'].create({
            'name': 'SEDAR Kalinga',
            'registry_no': 'IMO-9123456',
            'vessel_type': 'tug',
            'capacity': 3200.0,
        })
        self.assertEqual(vessel.status, 'active')
        self.assertEqual(vessel.vessel_type, 'tug')

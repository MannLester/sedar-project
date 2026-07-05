from odoo.tests.common import TransactionCase


class TestVoyageFuel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Masikap'})
        self.customer = self.env['res.partner'].create({'name': 'Batangas Port'})
        self.job = self.env['sedar.job.order'].create({
            'customer_id': self.customer.id,
            'vessel_id': self.vessel.id,
        })

    def test_voyage_log_links_to_job_vessel(self):
        log = self.env['sedar.voyage.log'].create({
            'job_order_id': self.job.id,
            'distance_nm': 8.5,
        })
        self.assertEqual(log.vessel_id, self.vessel)

    def test_fuel_cost_per_liter(self):
        log = self.env['sedar.fuel.log'].create({
            'vessel_id': self.vessel.id,
            'liters': 100.0,
            'cost': 6500.0,
        })
        self.assertEqual(log.cost_per_liter, 65.0)

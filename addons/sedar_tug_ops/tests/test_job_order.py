from odoo.tests.common import TransactionCase


class TestJobOrder(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Bantay'})
        self.customer = self.env['res.partner'].create({'name': 'Manila Port Authority'})

    def test_create_and_dispatch(self):
        job = self.env['sedar.job.order'].create({
            'customer_id': self.customer.id,
            'vessel_id': self.vessel.id,
            'origin_port': 'Manila South Harbor',
            'destination_port': 'Batangas Port',
        })
        self.assertEqual(job.state, 'requested')
        self.assertNotEqual(job.name, 'New')
        job.action_dispatch()
        self.assertEqual(job.state, 'dispatched')
        job.action_start()
        self.assertEqual(job.state, 'in_progress')
        job.action_complete()
        self.assertEqual(job.state, 'completed')

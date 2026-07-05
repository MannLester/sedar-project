from odoo.tests.common import TransactionCase


class TestTowageBilling(TransactionCase):

    def test_create_invoice_marks_job_billed(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Tagumpay'})
        customer = self.env['res.partner'].create({'name': 'Subic Bay Port'})
        job = self.env['sedar.job.order'].create({
            'customer_id': customer.id,
            'vessel_id': vessel.id,
        })
        bill = self.env['sedar.towage.billing'].create({
            'job_order_id': job.id,
            'rate_basis': 'hour',
            'hours': 2.5,
            'rate': 10000.0,
        })
        self.assertEqual(bill.amount, 25000.0)
        bill.action_create_invoice()
        self.assertTrue(bill.invoice_id)
        self.assertEqual(job.state, 'billed')

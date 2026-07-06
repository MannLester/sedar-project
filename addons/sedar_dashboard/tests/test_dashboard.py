from datetime import timedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestDashboard(TransactionCase):

    def test_kpis_compute(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Kalinga'})
        customer = self.env['res.partner'].create({'name': 'Manila South Harbor'})
        self.env['sedar.job.order'].create({
            'customer_id': customer.id,
            'vessel_id': vessel.id,
        })
        self.env['sedar.hsse.incident'].create({'description': 'Open incident'})
        self.env['sedar.hsse.permit'].create({
            'name': 'PCG Permit',
            'permit_type': 'Permit',
            'expiry_date': Date.today() + timedelta(days=5),
        })
        dashboard = self.env['sedar.dashboard'].create({})
        self.assertGreaterEqual(dashboard.active_jobs, 1)
        self.assertGreaterEqual(dashboard.vessel_utilization, 0.0)
        self.assertGreaterEqual(dashboard.open_incidents, 1)
        self.assertGreaterEqual(dashboard.expiring_documents, 1)

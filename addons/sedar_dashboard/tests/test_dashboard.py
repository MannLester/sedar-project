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
        dashboard = self.env['sedar.dashboard'].create({})
        self.assertGreaterEqual(dashboard.active_jobs, 1)
        self.assertGreaterEqual(dashboard.vessel_utilization, 0.0)
        self.assertGreaterEqual(dashboard.open_incidents, 1)
        self.assertGreaterEqual(dashboard.expiring_documents, 0)

    def test_owner_snapshot_is_live_and_drillable(self):
        vessel = self.env['sedar.vessel'].create({
            'name': 'SEDAR Owner Test',
            'status': 'dry_dock',
        })
        snapshot = self.env['sedar.dashboard'].get_owner_snapshot()
        self.assertTrue(snapshot['generated_at'])
        self.assertTrue(snapshot['metrics'])
        self.assertTrue(snapshot['alerts'])
        self.assertIn(vessel.id, [item['id'] for item in snapshot['vessels']])
        self.assertTrue(all('action' in item for item in snapshot['alerts']))

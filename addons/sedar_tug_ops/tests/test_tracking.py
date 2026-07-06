from odoo.tests.common import TransactionCase


class TestTracking(TransactionCase):

    def test_tracking_log_updates_vessel_latest_position(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Matatag'})
        log = self.env['sedar.vessel.tracking.log'].create({
            'vessel_id': vessel.id,
            'latitude': 14.5833,
            'longitude': 120.9667,
            'speed_knots': 6.5,
            'course_degrees': 210.0,
            'source': 'ais',
            'port_area': 'Manila Bay',
        })
        self.assertAlmostEqual(log.vessel_id.current_latitude, 14.5833, places=4)
        self.assertAlmostEqual(log.vessel_id.current_longitude, 120.9667, places=4)
        self.assertEqual(vessel.tracking_status, 'online')

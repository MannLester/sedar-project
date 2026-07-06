from datetime import timedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestHsse(TransactionCase):

    def test_incident_near_miss_and_risk(self):
        incident = self.env['sedar.hsse.incident'].create({
            'description': 'Mooring line snapped during berthing',
            'severity': 'medium',
        })
        self.assertEqual(incident.state, 'open')
        near_miss = self.env['sedar.hsse.near.miss'].create({
            'description': 'Crew member nearly slipped on wet deck',
            'risk_category': 'personnel',
        })
        self.assertEqual(near_miss.risk_category, 'personnel')
        risk = self.env['sedar.hsse.risk.assessment'].create({
            'activity': 'Towing',
            'hazard': 'Line parting',
            'likelihood': '3',
            'severity': '4',
        })
        self.assertEqual(risk.risk_score, 12)

    def test_inspection_lines_and_expiry_permit(self):
        inspection = self.env['sedar.hsse.inspection'].create({
            'inspection_type': 'vessel',
            'line_ids': [(0, 0, {'item': 'Fire extinguishers charged', 'result': 'pass'})],
        })
        self.assertEqual(len(inspection.line_ids), 1)
        permit = self.env['sedar.hsse.permit'].create({
            'name': 'Certificate of Vessel Safety',
            'permit_type': 'Safety',
            'expiry_date': Date.today() + timedelta(days=10),
        })
        self.assertEqual(permit.expiry_status, 'warning')

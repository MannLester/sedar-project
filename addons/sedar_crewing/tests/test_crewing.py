from datetime import timedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestCrewing(TransactionCase):

    def setUp(self):
        super().setUp()
        employee = self.env['hr.employee'].create({'name': 'Juan Dela Cruz'})
        self.vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Bagwis'})
        self.crew = self.env['sedar.crew.member'].create({
            'employee_id': employee.id,
            'rank': 'Master',
            'vessel_id': self.vessel.id,
        })

    def test_roster_rotation_cert_medical_leave(self):
        self.assertEqual(self.crew.name, 'Juan Dela Cruz')
        rotation = self.env['sedar.crew.rotation'].create({
            'crew_id': self.crew.id,
            'vessel_id': self.vessel.id,
            'onboard_date': Date.today(),
        })
        self.assertEqual(rotation.state, 'planned')
        cert = self.env['sedar.crew.certification'].create({
            'crew_id': self.crew.id,
            'cert_type': 'STCW Basic Safety Training',
            'expiry_date': Date.today() + timedelta(days=20),
        })
        self.assertEqual(cert.expiry_status, 'warning')
        medical = self.env['sedar.crew.medical'].create({
            'crew_id': self.crew.id,
            'expiry_date': Date.today() + timedelta(days=365),
        })
        self.assertTrue(medical.fit_for_duty)
        leave = self.env['sedar.crew.leave'].create({
            'crew_id': self.crew.id,
            'date_from': Date.today(),
            'date_to': Date.today() + timedelta(days=7),
        })
        self.assertEqual(leave.state, 'draft')

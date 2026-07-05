from datetime import timedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestExpiryMixin(TransactionCase):

    def _make_concrete_model_record(self, expiry_date):
        if 'sedar.hsse.permit' not in self.env:
            self.skipTest('sedar.hsse.permit is not available until sedar_hsse is loaded')
        return self.env['sedar.hsse.permit'].create({
            'name': 'Test Permit',
            'expiry_date': expiry_date,
        })

    def test_expired_status(self):
        rec = self._make_concrete_model_record(Date.today() - timedelta(days=1))
        self.assertEqual(rec.expiry_status, 'expired')

    def test_warning_status(self):
        rec = self._make_concrete_model_record(Date.today() + timedelta(days=10))
        self.assertEqual(rec.expiry_status, 'warning')

    def test_ok_status(self):
        rec = self._make_concrete_model_record(Date.today() + timedelta(days=365))
        self.assertEqual(rec.expiry_status, 'ok')

from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.fields import Date


class TestExpiryMixin(TransactionCase):

    def _make_concrete_model_record(self, expiry_date):
        # sedar.hsse.permit inherits the mixin; used here once it exists (Task 9).
        # Until then, this test exercises the mixin via a minimal throwaway model
        # is not possible in Odoo without a real table, so this test is written
        # against sedar.hsse.permit and only runs once Task 9 installs it.
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

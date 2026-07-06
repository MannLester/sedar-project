from datetime import timedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestDocControl(TransactionCase):

    def test_documents_share_expiry_logic(self):
        partner = self.env['res.partner'].create({'name': 'Malayan Insurance'})
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Kalinga'})
        contract = self.env['sedar.doc.contract'].create({
            'name': 'Fuel Supply Agreement 2026',
            'partner_id': partner.id,
            'contract_type': 'Supply',
            'expiry_date': Date.today() - timedelta(days=1),
        })
        self.assertEqual(contract.expiry_status, 'expired')
        vessel_cert = self.env['sedar.doc.vessel.cert'].create({
            'vessel_id': vessel.id,
            'cert_type': 'Certificate of Vessel Registry',
            'expiry_date': Date.today() + timedelta(days=20),
        })
        self.assertEqual(vessel_cert.expiry_status, 'warning')
        insurance = self.env['sedar.doc.insurance'].create({
            'policy_no': 'MARINE-2026-0042',
            'insurer': 'Malayan Insurance',
            'coverage_type': 'Hull and Machinery',
            'expiry_date': Date.today() + timedelta(days=365),
        })
        self.assertEqual(insurance.expiry_status, 'ok')
        doc = self.env['sedar.doc.record'].create({
            'name': 'Board Resolution No. 2026-05',
            'category': 'board_resolution',
        })
        self.assertEqual(doc.expiry_status, 'ok')

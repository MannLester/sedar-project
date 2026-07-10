from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestDocumentWorkflow(TransactionCase):
    def test_review_approval_and_renewal(self):
        contract = self.env['sedar.document.control'].create({
            'name': 'Towage Contract',
            'document_type': 'contract',
            'approval_status': 'draft',
            'expiry_date': fields.Date.add(fields.Date.today(), days=90),
            'attachment': b'dGVzdA==',
        })
        contract.action_submit_review()
        contract.action_approve_document()
        self.assertEqual(contract.approval_status, 'approved')
        action = contract.action_start_renewal()
        renewed = self.env['sedar.document.control'].browse(action['res_id'])
        self.assertEqual(renewed.version, '2.0')
        self.assertEqual(renewed.previous_version_id, contract)
        self.assertFalse(renewed.attachment)

    def test_attachment_and_rejection_notes_are_required(self):
        document = self.env['sedar.document.control'].create({
            'name': 'Board Resolution',
            'document_type': 'board_resolution',
            'approval_status': 'draft',
        })
        with self.assertRaises(UserError):
            document.action_submit_review()
        document.attachment = b'dGVzdA=='
        document.action_submit_review()
        with self.assertRaises(UserError):
            document.action_reject_document()
        document.workflow_notes = 'Correct the reference number.'
        document.action_reject_document()
        self.assertEqual(document.approval_status, 'draft')

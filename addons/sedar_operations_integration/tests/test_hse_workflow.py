from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestHseWorkflow(TransactionCase):
    def test_failed_inspection_creates_action(self):
        inspection = self.env['sedar.hsse.inspection'].create({
            'name': 'Deck inspection',
            'line_ids': [(0, 0, {'item': 'Emergency light', 'result': 'fail'})],
        })
        inspection.action_start()
        inspection.action_finish()
        self.assertEqual(inspection.state, 'action')
        self.assertEqual(len(inspection.action_ids), 1)

    def test_risk_requires_controls_and_lower_residual_score(self):
        risk = self.env['sedar.hsse.risk.assessment'].create({
            'activity': 'Towage',
            'hazard': 'Line failure',
            'likelihood': '3',
            'severity': '4',
        })
        with self.assertRaises(UserError):
            risk.action_submit()
        risk.mitigation = 'Inspect and replace tow lines before departure.'
        risk.action_submit()
        risk.action_approve()
        risk.action_mark_mitigated()
        self.assertEqual(risk.state, 'mitigated')

    def test_corrective_action_needs_completion_note(self):
        incident = self.env['sedar.hsse.incident'].create({'description': 'Test incident'})
        action = self.env['sedar.hsse.corrective.action'].create({
            'name': 'Test action',
            'incident_id': incident.id,
            'due_date': fields.Date.context_today(self),
        })
        action.action_start()
        with self.assertRaises(UserError):
            action.action_done()
        action.completion_note = 'Checked and closed.'
        action.action_done()
        incident.action_investigate()
        incident.action_close()
        self.assertEqual(incident.state, 'closed')

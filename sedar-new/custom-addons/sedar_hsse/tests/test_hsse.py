from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSedarHsse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "HSSE Test User",
            "login": "hsse.user@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_hsse.group_sedar_hsse_user").id,
            ])],
        })
        cls.manager = cls.env["res.users"].create({
            "name": "HSSE Test Manager",
            "login": "hsse.manager@test.example",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("sedar_hsse.group_sedar_hsse_manager").id,
            ])],
        })

    def test_incident_requires_verified_actions_before_closure(self):
        incident = self.env["sedar.hsse.incident"].create({
            "incident_type": "incident",
            "category": "operation",
            "severity": "critical",
            "summary": "Test incident.",
            "investigation_summary": "Investigation complete.",
            "root_cause": "Procedure gap.",
        })
        action = self.env["sedar.hsse.corrective.action"].create({
            "name": "Test corrective action",
            "incident_id": incident.id,
            "assigned_user_id": self.manager.id,
            "due_date": date.today(),
            "severity": "critical",
            "critical_control": True,
            "description": "Correct the procedure gap.",
        })

        with self.assertRaises(UserError):
            incident.with_user(self.manager).action_verify_close()

        action.completion_note = "Completed."
        action.action_mark_done()
        action.with_user(self.manager).action_verify()
        incident.with_user(self.manager).action_verify_close()

        self.assertEqual(incident.state, "verified")
        self.assertFalse(action.operational_exception)

    def test_non_manager_cannot_approve_risk_assessment(self):
        risk = self.env["sedar.hsse.risk.assessment"].create({
            "activity": "Test operation",
            "hazard": "Test hazard",
            "existing_controls": "Existing controls.",
            "likelihood": 2,
            "impact": 3,
            "owner_id": self.user.id,
        })
        with self.assertRaises(AccessError):
            risk.with_user(self.user).action_approve()

    def test_overdue_finding_and_expired_permit_create_visible_exceptions(self):
        inspection = self.env["sedar.hsse.inspection"].create({
            "inspection_type": "vessel",
            "inspector_id": self.manager.id,
            "summary": "Test inspection.",
        })
        finding = self.env["sedar.hsse.inspection.finding"].create({
            "inspection_id": inspection.id,
            "name": "Overdue finding",
            "severity": "critical",
            "assigned_user_id": self.manager.id,
            "due_date": date.today() - timedelta(days=1),
            "description": "Critical overdue finding.",
        })
        finding.action_create_corrective_action()

        self.assertTrue(finding.is_overdue)
        self.assertTrue(finding.corrective_action_id.operational_exception)
        self.assertEqual(inspection.overdue_finding_count, 1)

        permit = self.env["sedar.hsse.permit"].create({
            "permit_type": "hot_work",
            "permit_number": "TEST-PERMIT-001",
            "valid_from": date.today() - timedelta(days=10),
            "valid_until": date.today() - timedelta(days=1),
            "required_for_operations": True,
        })

        self.assertTrue(permit.is_expired)
        self.assertTrue(permit.operational_exception)
        self.assertEqual(permit.state, "expired")

        with self.assertRaises(ValidationError):
            self.env["sedar.hsse.permit"].create({
                "permit_type": "hot_work",
                "permit_number": "TEST-PERMIT-002",
                "valid_from": date.today(),
                "valid_until": date.today() - timedelta(days=1),
            })

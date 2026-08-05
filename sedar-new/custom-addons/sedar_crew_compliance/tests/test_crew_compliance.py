import base64
from datetime import datetime

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestCrewCompliance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compliance_manager = new_test_user(
            cls.env,
            login="sedar_crew_compliance_manager",
            groups="base.group_user,sedar_crew_compliance.group_crew_compliance_manager",
        )
        cls.partner = cls.env["res.partner"].create({"name": "Crew Compliance Client"})
        cls.port = cls.env["sedar.marine.port"].create({"name": "Crew Compliance Port", "code": "CCP"})
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Crew Compliance Assist",
            "code": "CCA",
            "pricing_basis": "per_service",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Crew Compliance Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Crew Compliance Tug",
            "registration_number": "CCA-TUG",
            "tug_class_id": cls.tug_class.id,
            "availability_status": "available",
        })
        cls.rank = cls.env["sedar.crew.rank"].create({"name": "Crew Compliance Master", "code": "CCM"})
        cls.certificate_type = cls.env["sedar.crew.certificate.type"].create({
            "name": "Crew Compliance STCW",
            "code": "CC-STCW",
        })
        cls.medical_type = cls.env["sedar.crew.certificate.type"].create({
            "name": "Crew Compliance Medical",
            "code": "CC-MED",
        })
        cls.employee = cls.env["hr.employee"].create({"name": "Crew Compliance Employee"})
        cls.profile = cls.env["sedar.crew.profile"].create({
            "employee_id": cls.employee.id,
            "employee_number": "CC-CREW-001",
            "rank_id": cls.rank.id,
            "home_tugboat_id": cls.tug.id,
            "availability_status": "available",
        })

    def _make_assignment(self):
        order = self.env["sedar.marine.service.order"].create({
            "client_id": self.partner.id,
            "assisted_vessel_name": "MV Crew Compliance",
            "service_type_id": self.service.id,
            "number_of_tugs": 1,
            "scope_of_work": "Credential readiness test.",
            "port_id": self.port.id,
            "requested_start": datetime(2026, 9, 1, 8, 0, 0),
            "estimated_duration_hours": 2,
            "state": "planning",
        })
        tug_assignment = self.env["sedar.tug.assignment"].create({
            "order_id": order.id,
            "tugboat_id": self.tug.id,
        })
        requirement = self.env["sedar.manning.requirement"].create({
            "tug_assignment_id": tug_assignment.id,
            "rank_id": self.rank.id,
            "required_count": 1,
            "required_certificate_type_ids": [(6, 0, [self.certificate_type.id])],
        })
        assignment = self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement.id,
            "crew_profile_id": self.profile.id,
        })
        return order, assignment

    def _make_certificate(self, certificate_type=None):
        return self.env["sedar.crew.certificate"].create({
            "crew_profile_id": self.profile.id,
            "certificate_type_id": (certificate_type or self.certificate_type).id,
            "certificate_number": "CC-CERT-001",
            "issue_date": "2026-01-01",
            "expiry_date": "2027-01-01",
        })

    def _complete_evidence_request(self, request):
        for value in request.value_ids:
            technical_name = value.field_id.technical_name
            if technical_name == "evidence_attachment":
                value.write({
                    "value_binary": base64.b64encode(b"credential evidence"),
                    "value_filename": "credential.pdf",
                })
            elif technical_name == "certificate_number":
                value.value_text = "CC-CERT-RENEWED"
            elif technical_name == "expiry_date":
                value.value_date = "2027-12-31"
        request.action_submit()
        request.action_review()
        request.action_approve()

    def test_unverified_required_credential_blocks_service_order_readiness(self):
        certificate = self._make_certificate()
        certificate.with_user(self.compliance_manager).write({"sedar_verification_state": "requested"})
        _order, assignment = self._make_assignment()

        self.assertFalse(assignment.is_eligible)
        self.assertIn("unverified", assignment.eligibility_reason)

        certificate.with_context(sedar_compliance_action=True).write({"sedar_verification_state": "verified"})
        assignment.invalidate_recordset()
        self.assertTrue(assignment.is_eligible)

    def test_renewal_request_uses_controlled_document_and_verification_sync(self):
        certificate = self._make_certificate()
        certificate.with_user(self.compliance_manager).action_sedar_request_renewal()
        request = certificate.sedar_document_request_id

        self.assertTrue(request)
        self.assertEqual(request.document_type_id.code, "CREW-CRED-EVIDENCE")
        self.assertEqual(request.state, "in_progress")
        self.assertEqual(certificate.sedar_verification_state, "requested")

        self._complete_evidence_request(request)
        certificate.with_user(self.compliance_manager).action_sedar_sync_from_document()

        self.assertEqual(certificate.sedar_verification_state, "verified")
        self.assertEqual(certificate.certificate_number, "CC-CERT-RENEWED")
        self.assertEqual(str(certificate.expiry_date), "2027-12-31")
        self.assertEqual(certificate.sedar_verified_by_id, self.compliance_manager)

    def test_medical_record_is_classified_and_visible_for_renewal(self):
        medical = self._make_certificate(self.medical_type)

        self.assertTrue(medical.sedar_is_medical)
        self.assertEqual(medical.sedar_expiry_state, "valid")

        medical.with_user(self.compliance_manager).action_sedar_request_renewal()
        self.assertEqual(medical.sedar_document_request_id.document_type_id.code, "CREW-CRED-EVIDENCE")


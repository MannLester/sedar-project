from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestRecruitmentCrewingOnboarding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hr_manager = new_test_user(
            cls.env,
            login="sedar_crew_onboarding_hr_manager",
            groups="base.group_user,hr_recruitment.group_hr_recruitment_manager",
        )
        cls.crewing_manager = new_test_user(
            cls.env,
            login="sedar_crew_onboarding_crewing_manager",
            groups="base.group_user,sedar_recruitment_crewing.group_crewing_manager",
        )
        cls.department = cls.env["hr.department"].create({"name": "Crew Onboarding Test Department"})
        cls.rank = cls.env["sedar.crew.rank"].create({"name": "Crew Onboarding Chief Engineer", "code": "COB-CHENG"})
        cls.job = cls.env["hr.job"].create({
            "name": "Crew Onboarding Chief Engineer",
            "department_id": cls.department.id,
        })
        cls.cert_stcw = cls.env["sedar.crew.certificate.type"].create({"name": "Crew Onboarding STCW", "code": "COB-STCW"})
        cls.cert_medical = cls.env["sedar.crew.certificate.type"].create({"name": "Crew Onboarding Medical", "code": "COB-MED"})
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Crew Onboarding Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Crew Onboarding Tug",
            "registration_number": "COB-TUG-001",
            "tug_class_id": cls.tug_class.id,
        })
        cls.request = cls.env["sedar.manpower.request"].create({
            "department_id": cls.department.id,
            "requested_by": cls.env.user.id,
            "business_justification": "Test marine crew onboarding request.",
            "state": "position_open",
        })
        cls.line = cls.env["sedar.manpower.request.line"].create({
            "request_id": cls.request.id,
            "crew_rank_id": cls.rank.id,
            "job_id": cls.job.id,
            "request_type": "permanent",
            "quantity": 1,
            "approved_quantity": 1,
            "required_date": fields.Date.context_today(cls.env.company),
            "required_certificate_type_ids": [(6, 0, [cls.cert_stcw.id, cls.cert_medical.id])],
        })
        cls.vacancy = cls.env["sedar.job.vacancy"].create({
            "request_line_id": cls.line.id,
            "job_id": cls.job.id,
            "crew_rank_id": cls.rank.id,
            "department_id": cls.department.id,
            "employment_type": "permanent",
            "approved_openings": 1,
            "opening_date": fields.Date.context_today(cls.env.company),
            "website_title": cls.job.name,
            "publication_state": "internal",
            "state": "open",
        })
        cls.line.vacancy_id = cls.vacancy.id

    def _ready_marine_employee(self):
        applicant = self.env["hr.applicant"].create({
            "partner_name": "Crew Onboarding Applicant",
            "email_from": "crew.onboarding@sedar.example.com",
            "job_id": self.job.id,
            "department_id": self.department.id,
            "user_id": self.hr_manager.id,
            "sedar_vacancy_id": self.vacancy.id,
            "stage_id": self.env.ref("sedar_recruitment_operations.stage_requirements_verified").id,
            "sedar_public_status": "offer",
        })
        offer = self.env["sedar.applicant.offer"].create({
            "applicant_id": applicant.id,
            "state": "accepted",
            "decision": "hire",
            "offered_position": self.job.name,
            "employment_type": "probationary",
            "proposed_start_date": "2026-09-01",
            "expiry_date": "2026-09-15",
            "offer_summary": "Crew onboarding test accepted offer.",
            "issued_by_id": self.hr_manager.id,
            "issued_at": fields.Datetime.now(),
            "accepted_at": fields.Datetime.now(),
            "accepted_by_id": self.hr_manager.id,
            "acceptance_source": "internal_hr_confirmation",
        })
        request = self.env["sedar.document.request"].create({
            "name": "ADM-5 Employment Requirements - Crew Onboarding",
            "document_type_id": self.env.ref("sedar_document_control.document_type_adm_5").id,
            "subject_name": applicant.partner_name,
            "subject_reference": applicant.sedar_reference,
            "assigned_user_id": self.hr_manager.id,
            "due_date": "2026-09-01",
            "state": "approved",
            "applicant_id": applicant.id,
            "sedar_request_purpose": "employment_requirements",
            "applicant_visible": True,
        })
        applicant.with_user(self.hr_manager).action_sedar_create_employee_profile()
        return applicant, applicant.employee_id, offer, request

    def test_marine_employee_conversion_creates_one_crewing_onboarding_case(self):
        applicant, employee, _offer, _request = self._ready_marine_employee()

        onboarding = self.env["sedar.crew.onboarding"].search([("employee_id", "=", employee.id)])
        self.assertEqual(len(onboarding), 1)
        self.assertEqual(onboarding.applicant_id, applicant)
        self.assertEqual(onboarding.vacancy_id, self.vacancy)
        self.assertEqual(onboarding.rank_id, self.rank)
        self.assertEqual(onboarding.required_certificate_type_ids, self.cert_stcw | self.cert_medical)
        self.assertFalse(onboarding.deployment_eligible)
        self.assertIn("Crew Profile not created", onboarding.blocker_summary)

        applicant.with_user(self.hr_manager).action_sedar_create_employee_profile()
        self.assertEqual(self.env["sedar.crew.onboarding"].search_count([("employee_id", "=", employee.id)]), 1)

    def test_crewing_marks_profile_eligible_only_after_required_readiness(self):
        _applicant, employee, _offer, _request = self._ready_marine_employee()
        onboarding = self.env["sedar.crew.onboarding"].search([("employee_id", "=", employee.id)], limit=1)

        onboarding.with_user(self.crewing_manager).action_mark_deployment_eligible()
        self.assertEqual(onboarding.state, "blocked")

        onboarding.write({"home_tugboat_id": self.tug.id})
        onboarding.with_user(self.crewing_manager).action_create_crew_profile()
        self.assertEqual(onboarding.crew_profile_id.availability_status, "unavailable")
        self.assertFalse(onboarding.deployment_eligible)
        self.assertEqual(onboarding.missing_certificate_type_ids, self.cert_stcw | self.cert_medical)

        for certificate_type in onboarding.required_certificate_type_ids:
            self.env["sedar.crew.certificate"].create({
                "crew_profile_id": onboarding.crew_profile_id.id,
                "certificate_type_id": certificate_type.id,
                "certificate_number": "COB-%s-%s" % (certificate_type.code, employee.id),
                "issue_date": "2026-08-01",
                "expiry_date": "2027-08-01",
            })
        onboarding.invalidate_recordset()
        onboarding.with_user(self.crewing_manager).action_mark_deployment_eligible()

        self.assertTrue(onboarding.deployment_eligible)
        self.assertEqual(onboarding.state, "deployment_eligible")
        self.assertEqual(onboarding.crew_profile_id.availability_status, "available")

    def test_non_marine_employee_does_not_create_crewing_onboarding(self):
        employee = self.env["hr.employee"].create({
            "name": "Non Marine Onboarding Employee",
            "department_id": self.department.id,
            "job_id": self.job.id,
        })
        onboarding = self.env["sedar.crew.onboarding"]._sedar_get_or_create_from_employee(employee)
        self.assertFalse(onboarding)

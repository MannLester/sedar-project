from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestApplicantEmployeeOnboarding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hr_manager = new_test_user(
            cls.env,
            login="sedar_onboarding_test_hr_manager",
            groups="base.group_user,hr_recruitment.group_hr_recruitment_manager,sedar_manpower_planning.group_hr_manager",
        )
        cls.department = cls.env["hr.department"].create({"name": "Onboarding Test Marine Department"})
        cls.rank = cls.env["sedar.crew.rank"].create({"name": "Onboarding Test Engineer", "code": "ONB-ENG"})
        cls.job = cls.env["hr.job"].create({
            "name": "Onboarding Test Chief Engineer",
            "department_id": cls.department.id,
        })
        cls.request = cls.env["sedar.manpower.request"].create({
            "department_id": cls.department.id,
            "requested_by": cls.env.user.id,
            "business_justification": "Test headcount request.",
            "operational_impact": "Test Service Order staffing impact.",
            "state": "approved",
        })
        cls.line = cls.env["sedar.manpower.request.line"].create({
            "request_id": cls.request.id,
            "crew_rank_id": cls.rank.id,
            "job_id": cls.job.id,
            "request_type": "permanent",
            "quantity": 1,
            "approved_quantity": 1,
            "required_date": fields.Date.context_today(cls.env.company),
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

    def _make_ready_applicant(self, name="Onboarding Test Applicant"):
        applicant = self.env["hr.applicant"].create({
            "partner_name": name,
            "email_from": "onboarding.test@sedar.example.com",
            "job_id": self.job.id,
            "department_id": self.department.id,
            "sedar_vacancy_id": self.vacancy.id,
            "user_id": self.hr_manager.id,
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
            "offer_summary": "Test accepted offer.",
            "issued_by_id": self.hr_manager.id,
            "issued_at": fields.Datetime.now(),
            "accepted_at": fields.Datetime.now(),
            "accepted_by_id": self.hr_manager.id,
            "acceptance_source": "internal_hr_confirmation",
        })
        request = self.env["sedar.document.request"].create({
            "name": "ADM-5 Employment Requirements - Test",
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
        return applicant, offer, request

    def test_conversion_requires_accepted_offer_and_approved_adm5(self):
        applicant, offer, request = self._make_ready_applicant("Onboarding Gate Test")
        offer.write({"state": "issued", "accepted_at": False})
        with self.assertRaises(UserError):
            applicant.action_sedar_create_employee_profile()

        offer.write({"state": "accepted", "accepted_at": fields.Datetime.now()})
        request.write({"state": "submitted"})
        with self.assertRaises(UserError):
            applicant.action_sedar_create_employee_profile()

    def test_employee_conversion_is_traceable_and_fulfills_headcount_once(self):
        applicant, offer, request = self._make_ready_applicant("Onboarding Conversion Test")
        applicant.with_user(self.hr_manager).action_sedar_create_employee_profile()
        employee = applicant.employee_id

        self.assertTrue(employee)
        self.assertEqual(employee.sedar_source_applicant_id, applicant)
        self.assertEqual(employee.sedar_source_vacancy_id, self.vacancy)
        self.assertEqual(employee.sedar_source_offer_id, offer)
        self.assertEqual(employee.sedar_source_requirement_request_id, request)
        self.assertEqual(employee.sedar_employment_type, "probationary")
        self.assertEqual(employee.sedar_planned_start_date, fields.Date.to_date("2026-09-01"))
        self.assertEqual(employee.sedar_onboarding_state, "pending")
        self.assertEqual(employee.sedar_onboarding_owner_id, self.hr_manager)
        self.assertIn("Crew Profile onboarding", employee.sedar_onboarding_checklist)
        self.assertEqual(self.vacancy.filled_openings, 1)
        self.assertEqual(self.vacancy.remaining_openings, 0)
        self.assertEqual(self.vacancy.state, "filled")
        self.assertEqual(self.request.state, "closed")

        employee_count = self.env["hr.employee"].search_count([("sedar_source_applicant_id", "=", applicant.id)])
        applicant.with_user(self.hr_manager).action_sedar_create_employee_profile()
        self.assertEqual(
            self.env["hr.employee"].search_count([("sedar_source_applicant_id", "=", applicant.id)]),
            employee_count,
        )
        self.assertEqual(self.vacancy.filled_openings, 1)


@tagged("post_install", "-at_install")
class TestManpowerVacancyOpening(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hr_manager = new_test_user(
            cls.env,
            login="sedar_vacancy_opening_test_hr_manager",
            groups="base.group_user,sedar_manpower_planning.group_hr_manager",
        )
        cls.department = cls.env["hr.department"].create({"name": "Vacancy Opening Test Department"})
        cls.port = cls.env["sedar.marine.port"].create({"name": "Vacancy Test Port", "code": "VAC-PORT"})
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Vacancy Test Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Vacancy Test Tug",
            "registration_number": "VAC-TUG-001",
            "tug_class_id": cls.tug_class.id,
        })
        cls.service = cls.env["sedar.marine.service.type"].create({"name": "Vacancy Test Service", "code": "VAC-SVC"})
        cls.rank = cls.env["sedar.crew.rank"].create({"name": "Vacancy Test Rank", "code": "VAC-RANK"})
        cls.job = cls.env["hr.job"].create({"name": "Vacancy Test Marine Rank", "department_id": cls.department.id})
        cls.order = cls.env["sedar.marine.service.order"].create({
            "client_id": cls.env["res.partner"].create({"name": "Vacancy Test Client"}).id,
            "assisted_vessel_name": "MV Vacancy Test",
            "service_type_id": cls.service.id,
            "number_of_tugs": 1,
            "scope_of_work": "Vacancy opening test.",
            "port_id": cls.port.id,
            "requested_start": fields.Datetime.now(),
            "estimated_duration_hours": 2,
        })
        cls.assignment = cls.env["sedar.tug.assignment"].create({
            "order_id": cls.order.id,
            "tugboat_id": cls.tug.id,
        })
        cls.requirement = cls.env["sedar.manning.requirement"].create({
            "tug_assignment_id": cls.assignment.id,
            "rank_id": cls.rank.id,
            "required_count": 1,
        })

    def test_opening_vacancy_does_not_resolve_operational_shortage(self):
        shortage = self.env["sedar.crew.shortage"].create({
            "requirement_id": self.requirement.id,
            "missing_count": 1,
            "reason": "no_qualified",
            "review_state": "escalated",
            "root_cause": "permanent_headcount",
            "resolution_action": "manpower_request",
            "status": "open",
        })
        request = self.env["sedar.manpower.request"].create({
            "department_id": self.department.id,
            "requested_by": self.env.user.id,
            "business_justification": "Open position without resolving operational shortage.",
            "operational_impact": "Service Order remains blocked until Crewing assigns qualified coverage.",
            "state": "approved",
        })
        self.env["sedar.manpower.request.line"].create({
            "request_id": request.id,
            "crew_rank_id": self.rank.id,
            "job_id": self.job.id,
            "request_type": "permanent",
            "quantity": 1,
            "approved_quantity": 1,
            "required_date": fields.Date.context_today(self.env.company),
            "shortage_ids": [(6, 0, [shortage.id])],
        })

        request.with_user(self.hr_manager).action_open_vacancies()

        self.assertEqual(request.state, "position_open")
        self.assertEqual(shortage.review_state, "escalated")
        self.assertEqual(shortage.status, "open")
        self.assertFalse(shortage.resolved_at)


@tagged("post_install", "-at_install")
class TestRecruitmentControlHardening(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hr_manager = new_test_user(
            cls.env,
            login="sedar_hardening_hr_manager",
            groups="base.group_user,hr_recruitment.group_hr_recruitment_manager",
        )
        cls.recruiter = new_test_user(
            cls.env,
            login="sedar_hardening_recruiter",
            groups="base.group_user,hr_recruitment.group_hr_recruitment_user",
        )
        cls.interviewer = new_test_user(
            cls.env,
            login="sedar_hardening_interviewer",
            groups="base.group_user,hr_recruitment.group_hr_recruitment_user",
        )
        cls.other_recruiter = new_test_user(
            cls.env,
            login="sedar_hardening_other_recruiter",
            groups="base.group_user,hr_recruitment.group_hr_recruitment_user",
        )
        cls.department = cls.env["hr.department"].create({"name": "Hardening Test Department"})
        cls.job = cls.env["hr.job"].create({"name": "Hardening Test Marine Crew", "department_id": cls.department.id})

    def _make_applicant(self):
        return self.env["hr.applicant"].create({
            "partner_name": "Hardening Test Applicant",
            "email_from": "hardening.applicant@sedar.example.com",
            "job_id": self.job.id,
            "department_id": self.department.id,
            "user_id": self.recruiter.id,
            "stage_id": self.env.ref("sedar_recruitment_operations.stage_interview_completed").id,
            "sedar_public_status": "final_review",
        })

    def test_interview_visibility_is_limited_to_assigned_users_and_managers(self):
        applicant = self._make_applicant()
        interview = self.env["sedar.applicant.interview"].create({
            "name": "Hardening Interview",
            "applicant_id": applicant.id,
            "interview_type": "technical",
            "status": "scheduled",
            "start_datetime": "2026-09-01 09:00:00",
            "end_datetime": "2026-09-01 10:00:00",
            "coordinator_id": self.recruiter.id,
            "interviewer_ids": [(6, 0, [self.interviewer.id])],
        })

        self.assertEqual(
            self.env["sedar.applicant.interview"].with_user(self.interviewer).search([("id", "=", interview.id)]),
            interview,
        )
        self.assertFalse(
            self.env["sedar.applicant.interview"].with_user(self.other_recruiter).search([("id", "=", interview.id)])
        )
        self.assertEqual(
            self.env["sedar.applicant.interview"].with_user(self.hr_manager).search([("id", "=", interview.id)]),
            interview,
        )

    def test_confidential_recruitment_documents_are_limited_to_assigned_users_and_managers(self):
        applicant = self._make_applicant()
        request = self.env["sedar.document.request"].create({
            "name": "ADM-4A Background Inquiry - Hardening",
            "document_type_id": self.env.ref("sedar_document_control.document_type_adm_4a").id,
            "subject_name": applicant.partner_name,
            "subject_reference": applicant.sedar_reference,
            "assigned_user_id": self.recruiter.id,
            "applicant_id": applicant.id,
            "sedar_request_purpose": "background_check",
            "applicant_visible": False,
        })

        self.assertEqual(
            self.env["sedar.document.request"].with_user(self.recruiter).search([("id", "=", request.id)]),
            request,
        )
        self.assertFalse(
            self.env["sedar.document.request"].with_user(self.other_recruiter).search([("id", "=", request.id)])
        )
        self.assertEqual(
            self.env["sedar.document.request"].with_user(self.hr_manager).search([("id", "=", request.id)]),
            request,
        )
        self.assertFalse(
            self.env["sedar.document.value"].with_user(self.other_recruiter).search([("request_id", "=", request.id)])
        )

    def test_offer_issue_and_internal_acceptance_require_manager_and_record_audit(self):
        applicant = self._make_applicant()
        offer = self.env["sedar.applicant.offer"].create({
            "applicant_id": applicant.id,
            "decision": "hire",
            "offered_position": self.job.name,
            "employment_type": "probationary",
            "proposed_start_date": "2026-09-10",
            "expiry_date": "2026-09-05",
            "offer_summary": "Hardening test offer.",
        })

        with self.assertRaises(UserError):
            offer.with_user(self.recruiter).action_issue()

        offer.with_user(self.hr_manager).action_issue()

        with self.assertRaises(UserError):
            offer.with_user(self.recruiter).action_accept()

        offer.with_user(self.hr_manager).action_accept()
        self.assertEqual(offer.state, "accepted")
        self.assertEqual(offer.accepted_by_id, self.hr_manager)
        self.assertEqual(offer.acceptance_source, "internal_hr_confirmation")

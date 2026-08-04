import base64
from datetime import datetime

from odoo import Command, fields, models


MODULE = "sedar_recruitment_demo"


def _dt(day, hour=8, minute=0):
    return datetime(2026, 8, day, hour, minute)


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_ensure_recruitment_demo(self):
        env = self.env
        company = env.company
        department = env.ref("sedar_service_order_demo.department_operations")
        job = env.ref("sedar_service_order_demo.job_cheng")
        vacancy = env.ref("sedar_manpower_planning_demo.vacancy_chief_engineer")
        recruiter = self._sedar_demo_user(
            "user_hr_recruiter",
            "Demo HR Recruiter",
            "hr@sedar.demo",
            [
                "base.group_user",
                "hr_recruitment.group_hr_recruitment_user",
                "sedar_manpower_planning.group_hr_reviewer",
            ],
        )
        hr_manager = self._sedar_demo_user(
            "user_hr_manager",
            "Demo HR Manager",
            "hrmanager@sedar.demo",
            [
                "base.group_user",
                "hr_recruitment.group_hr_recruitment_manager",
                "sedar_manpower_planning.group_hr_manager",
                "sedar_manpower_planning.group_manpower_approver",
            ],
        )
        interviewer = self._sedar_demo_user(
            "user_interviewer",
            "Demo Technical Interviewer",
            "interviewer@sedar.demo",
            ["base.group_user", "hr_recruitment.group_hr_recruitment_user"],
        )

        common = {
            "job_id": job.id,
            "department_id": department.id,
            "company_id": company.id,
            "user_id": recruiter.id,
            "sedar_vacancy_id": vacancy.id,
            "sedar_document_type_id": env.ref("sedar_document_control.document_type_adm_3").id,
            "sedar_document_revision": "Demo ADM-3 source",
            "sedar_consent": True,
            "sedar_consent_at": _dt(17, 8),
        }
        specs = [
            {
                "xmlid": "applicant_new_review",
                "name": "Demo Applicant - New Review",
                "email": "applicant.new@sedar.demo",
                "phone": "+63 917 700 1001",
                "stage": "sedar_recruitment_operations.stage_under_review",
                "public_status": "under_review",
                "next_action": "Complete initial application review",
                "next_date": "2026-08-18",
                "message": "HR is reviewing this newly submitted ADM-3 application.",
                "intake_state": "submitted",
            },
            {
                "xmlid": "applicant_qualified",
                "name": "Demo Applicant - Qualified",
                "email": "applicant.qualified@sedar.demo",
                "phone": "+63 917 700 1002",
                "stage": "sedar_recruitment_operations.stage_qualified",
                "public_status": "shortlisted",
                "next_action": "Schedule applicant interview",
                "next_date": "2026-08-19",
                "message": "The application passed initial review and is ready for scheduling.",
                "intake_state": "under_review",
            },
            {
                "xmlid": "applicant_interview_scheduled",
                "name": "Demo Applicant - Interview Scheduled",
                "email": "applicant.scheduled@sedar.demo",
                "phone": "+63 917 700 1003",
                "stage": "sedar_recruitment_operations.stage_interview_scheduled",
                "public_status": "interview",
                "next_action": "Attend scheduled interview",
                "next_date": "2026-08-22",
                "message": "Interview is scheduled and awaiting applicant confirmation.",
                "interview": {
                    "xmlid": "interview_scheduled",
                    "status": "scheduled",
                    "start": _dt(22, 9),
                    "end": _dt(22, 10),
                },
            },
            {
                "xmlid": "applicant_reschedule_requested",
                "name": "Demo Applicant - Reschedule Requested",
                "email": "applicant.reschedule@sedar.demo",
                "phone": "+63 917 700 1004",
                "stage": "sedar_recruitment_operations.stage_interview_scheduled",
                "public_status": "interview",
                "next_action": "Review applicant reschedule request",
                "next_date": "2026-08-22",
                "message": "Applicant requested a new interview schedule.",
                "interview": {
                    "xmlid": "interview_reschedule_requested",
                    "status": "reschedule",
                    "start": _dt(22, 13),
                    "end": _dt(22, 14),
                    "note": "Applicant requested a later date because of travel from Cebu.",
                },
            },
            {
                "xmlid": "applicant_completed_interview",
                "name": "Demo Applicant - Completed Interview",
                "email": "applicant.completed@sedar.demo",
                "phone": "+63 917 700 1005",
                "stage": "sedar_recruitment_operations.stage_interview_completed",
                "public_status": "final_review",
                "next_action": "Complete background inquiry and company orientation",
                "next_date": "2026-08-23",
                "message": "Interview is complete and awaiting internal HR controls.",
                "interview": {
                    "xmlid": "interview_completed",
                    "status": "completed",
                    "start": _dt(21, 9),
                    "end": _dt(21, 10),
                    "result": "recommended",
                    "submitted_appraisal": True,
                },
            },
            {
                "xmlid": "applicant_pending_requirements",
                "name": "Demo Applicant - Pending ADM-5",
                "email": "applicant.pending.requirements@sedar.demo",
                "phone": "+63 917 700 1006",
                "stage": "sedar_recruitment_operations.stage_requirements_requested",
                "public_status": "requirements",
                "next_action": "Wait for applicant employment requirements",
                "next_date": "2026-08-25",
                "message": "Applicant must submit ADM-5 employment requirements.",
                "requirements": {"xmlid": "request_pending_requirements", "state": "in_progress"},
            },
            {
                "xmlid": "applicant_verified_requirements",
                "name": "Demo Applicant - Verified Requirements",
                "email": "applicant.verified.requirements@sedar.demo",
                "phone": "+63 917 700 1007",
                "stage": "sedar_recruitment_operations.stage_requirements_verified",
                "public_status": "offer",
                "next_action": "Prepare employment offer / onboarding",
                "next_date": "2026-08-26",
                "message": "ADM-5 requirements are approved and the applicant is ready for employment action.",
                "requirements": {"xmlid": "request_verified_requirements", "state": "approved", "filled": True},
            },
            {
                "xmlid": "applicant_rejected",
                "name": "Demo Applicant - Rejected",
                "email": "applicant.rejected@sedar.demo",
                "phone": "+63 917 700 1008",
                "stage": "sedar_recruitment_operations.stage_rejected",
                "public_status": "closed",
                "next_action": False,
                "message": "Application has been closed after HR review.",
                "rejection": "Fictional demo rejection: minimum marine engineering experience was not met.",
            },
            {
                "xmlid": "applicant_withdrawn",
                "name": "Demo Applicant - Withdrawn",
                "email": "applicant.withdrawn@sedar.demo",
                "phone": "+63 917 700 1009",
                "stage": "sedar_recruitment_operations.stage_rejected",
                "public_status": "closed",
                "next_action": False,
                "message": "Applicant withdrew from the recruitment process.",
                "withdrawal": "Fictional demo withdrawal: applicant accepted another offer.",
            },
            {
                "xmlid": "applicant_converted_employee",
                "name": "Demo Applicant - Converted Employee",
                "email": "applicant.converted@sedar.demo",
                "phone": "+63 917 700 1010",
                "stage": "sedar_recruitment_operations.stage_employee_created",
                "public_status": "successful",
                "next_action": "Complete employee onboarding setup",
                "message": "Employee profile has been created for demonstration.",
                "requirements": {"xmlid": "request_converted_employee", "state": "approved", "filled": True},
                "employee": True,
            },
        ]

        for index, spec in enumerate(specs, start=1):
            applicant = self._sedar_demo_applicant(spec, common, index)
            self._sedar_demo_profile(applicant, spec, index)
            self._sedar_demo_supporting_document(applicant, spec, index)
            if spec.get("interview"):
                self._sedar_demo_interview(applicant, spec["interview"], recruiter, interviewer)
            if spec["public_status"] == "final_review":
                self._sedar_demo_recruitment_controls(applicant, hr_manager, "submitted")
            if spec["public_status"] in ("requirements", "offer", "successful"):
                self._sedar_demo_recruitment_controls(applicant, hr_manager, "approved")
            if spec.get("requirements"):
                self._sedar_demo_requirements(applicant, spec["requirements"], hr_manager)
            if spec.get("employee") and not applicant.employee_id:
                employee = self._sedar_record("hr.employee", "employee_converted_chief_engineer", {
                    "name": applicant.partner_name,
                    "department_id": department.id,
                    "job_id": job.id,
                    "work_email": "converted.chief.engineer@sedar-demo.example.com",
                    "company_id": company.id,
                })
                applicant.employee_id = employee.id
            self._sedar_prune_duplicate_portal_events(applicant)

        self._sedar_demo_portal_owner()
        return True

    def _sedar_demo_user(self, xmlid, name, login, groups):
        group_ids = [self.env.ref(group).id for group in groups]
        return self._sedar_record("res.users", xmlid, {
            "name": name,
            "login": login,
            "password": "recruitdemo",
            "company_id": self.env.company.id,
            "company_ids": [Command.set([self.env.company.id])],
            "group_ids": [Command.set(group_ids)],
        })

    def _sedar_demo_applicant(self, spec, common, sequence):
        vals = {
            **common,
            "partner_name": spec["name"],
            "email_from": spec["email"],
            "partner_phone": spec["phone"],
            "stage_id": self.env.ref(spec["stage"]).id,
            "sedar_public_status": spec["public_status"],
            "sedar_public_message": spec["message"],
            "sedar_action_required": spec["public_status"] == "requirements",
            "sedar_action_instructions": spec["message"] if spec["public_status"] == "requirements" else False,
            "sedar_next_action": spec.get("next_action"),
            "sedar_next_action_date": spec.get("next_date"),
            "sedar_intake_state": spec.get("intake_state", "under_review"),
            "sedar_reference": "APP-DEMO-%03d" % sequence,
            "sedar_tracking_token": "tracking-demo-%03d" % sequence,
            "sedar_claim_token": "claim-demo-%03d" % sequence,
            "sedar_claim_expires_at": _dt(30, 17),
            "sedar_status_updated_at": _dt(17 + min(sequence, 10), 9),
            "sedar_rejection_reason": spec.get("rejection"),
            "sedar_withdrawal_reason": spec.get("withdrawal"),
        }
        return self._sedar_record("hr.applicant", spec["xmlid"], vals)

    def _sedar_demo_profile(self, applicant, spec, sequence):
        profile = self._sedar_record("sedar.applicant.profile", "profile_%s" % spec["xmlid"], {
            "applicant_id": applicant.id,
            "family_name": "Demo%02d" % sequence,
            "given_name": "Applicant",
            "middle_name": "Recruitment",
            "date_of_birth": "1994-04-%02d" % min(sequence, 28),
            "place_of_birth": "Batangas City",
            "age": 32,
            "height": 170.0 + sequence,
            "weight": 68.0 + sequence,
            "civil_status": "single",
            "contact_information": "%s\n%s" % (spec["email"], spec["phone"]),
            "identity_documents": "Demo SIRB and license details for %s." % applicant.sedar_reference,
            "skills": "Marine engineering, watchkeeping, safety drills, and equipment inspection.",
            "training_entries": "STCW Basic Safety Training; Engine Room Resource Management.",
            "medical_entries": "Demo medical record available for HR review.",
            "emergency_contact": "Demo Emergency Contact / +63 917 700 2000",
            "certification_date": "2026-08-17",
            "electronic_signature": spec["name"],
            "signature_date": "2026-08-17",
        })
        applicant.sedar_profile_id = profile.id
        self._sedar_record("sedar.applicant.education", "education_%s" % spec["xmlid"], {
            "applicant_id": applicant.id,
            "school_name": "Philippine Merchant Marine Demo College",
            "course_name": "BS Marine Engineering",
            "date_from": "2012-06-01",
            "date_to": "2016-03-31",
            "english_knowledge": "Good",
        })
        self._sedar_record("sedar.applicant.employment", "employment_%s" % spec["xmlid"], {
            "applicant_id": applicant.id,
            "date_from": "2021-01-01",
            "date_to": "2026-07-31",
            "company_address": "Demo Harbor Services, Batangas City",
            "position": "Assistant Engineer",
            "reason_for_leaving": "Seeking career growth with SEDAR Tug Services.",
        })

    def _sedar_demo_supporting_document(self, applicant, spec, sequence):
        attachment = self._sedar_record("ir.attachment", "attachment_resume_%s" % spec["xmlid"], {
            "name": "resume-%s.txt" % applicant.sedar_reference.lower(),
            "res_model": "hr.applicant",
            "res_id": applicant.id,
            "type": "binary",
            "mimetype": "text/plain",
            "datas": base64.b64encode(
                ("Fictional resume attachment for %s." % applicant.partner_name).encode("utf-8")
            ).decode("ascii"),
        })
        self._sedar_record("sedar.applicant.document", "document_resume_%s" % spec["xmlid"], {
            "applicant_id": applicant.id,
            "attachment_id": attachment.id,
            "category": "resume",
            "verification_state": "verified" if sequence in (7, 10) else "pending",
        })

    def _sedar_demo_interview(self, applicant, spec, recruiter, interviewer):
        interview = self._sedar_record("sedar.applicant.interview", spec["xmlid"], {
            "name": "Interview - %s" % applicant.partner_name,
            "applicant_id": applicant.id,
            "interview_type": "technical",
            "status": spec["status"],
            "start_datetime": spec["start"],
            "end_datetime": spec["end"],
            "location": "SEDAR Demo HR Office",
            "coordinator_id": recruiter.id,
            "interviewer_ids": [Command.set([interviewer.id])],
            "applicant_confirmation_note": spec.get("note"),
            "result": spec.get("result"),
        })
        request = interview.appraisal_request_id or interview._create_appraisal_request()
        if spec.get("submitted_appraisal"):
            self._fill_document_request(request, {
                "applicant_name": {"value_text": applicant.partner_name},
                "position_applied": {"value_text": applicant.sedar_vacancy_id.website_title},
                "interview_date": {"value_date": fields.Date.to_date(spec["start"])},
                "interviewer": {"value_text": interviewer.name},
                "initial_expression": {"value_text": "Professional and clear during the demonstration interview."},
                "skills_impression": {"value_text": "Relevant marine engineering background for the demo vacancy."},
                "recommendation": {"value_text": "Recommended for demonstration purposes."},
                "action_taken": {"value_text": "Proceed to HR decision review."},
            })
            request.write({"state": "submitted"})
        return interview

    def _sedar_demo_requirements(self, applicant, spec, hr_manager):
        request = self._sedar_record("sedar.document.request", spec["xmlid"], {
            "name": "ADM-5 Employment Requirements - %s" % applicant.sedar_reference,
            "document_type_id": self.env.ref("sedar_document_control.document_type_adm_5").id,
            "subject_name": applicant.partner_name,
            "subject_reference": applicant.sedar_reference,
            "assigned_user_id": hr_manager.id,
            "due_date": "2026-08-25",
            "state": "draft",
            "applicant_id": applicant.id,
            "sedar_request_purpose": "employment_requirements",
            "applicant_visible": True,
            "notes": "Fictional ADM-5 request managed by sedar_recruitment_demo.",
        })
        values = {
            "employee_name": {"value_text": applicant.partner_name},
            "position": {"value_text": applicant.sedar_vacancy_id.website_title},
            "list_given_on": {"value_date": "2026-08-18"},
            "needed_on": {"value_date": "2026-08-25"},
            "requirement_checklist": {"value_text": "NBI Clearance; SSS E1/E4; ID; TIN ID; Transcript of Record; Medical Certificate; Employment Certificate; Photos; Community Tax Certificate; Birth Certificate; Police Clearance; Barangay Clearance; Proof of SSS, PhilHealth and Pag-IBIG."},
        }
        if spec.get("filled"):
            values["supporting_documents"] = {
                "value_binary": base64.b64encode(b"Fictional ADM-5 attachment package.").decode("ascii"),
                "value_filename": "adm-5-demo-package.txt",
            }
        self._fill_document_request(request, values)
        if request.state != spec["state"]:
            request.write({"state": spec["state"]})
        return request

    def _sedar_demo_recruitment_controls(self, applicant, hr_manager, state):
        background = self._sedar_record("sedar.document.request", "request_background_%s" % applicant.sedar_reference.lower().replace("-", "_"), {
            "name": "ADM-4A Background Inquiry - %s" % applicant.sedar_reference,
            "document_type_id": self.env.ref("sedar_document_control.document_type_adm_4a").id,
            "subject_name": applicant.partner_name,
            "subject_reference": applicant.sedar_reference,
            "assigned_user_id": hr_manager.id,
            "due_date": "2026-08-24",
            "state": "draft",
            "applicant_id": applicant.id,
            "sedar_request_purpose": "background_check",
            "applicant_visible": False,
            "notes": "Fictional confidential ADM-4A control managed by sedar_recruitment_demo.",
        })
        self._fill_document_request(background, {
            "correspondence_to": {"value_text": "Demo Previous Employer"},
            "inquiry_date": {"value_date": "2026-08-22"},
            "attention_to": {"value_text": "Demo HR / Crewing Records"},
            "reference": {"value_text": applicant.sedar_reference},
            "applicant_name": {"value_text": applicant.partner_name},
            "last_vessel": {"value_text": "M/T Demo Harbor Assist"},
            "position": {"value_text": applicant.sedar_vacancy_id.website_title},
            "evaluation_results": {"value_text": "Ability: Good; Conduct / Attitude: Good; Responsibility: Good; Technical Competence: Good; Health: Good; Overall Assessment: Good."},
            "rehirable": {"value_selection": "Yes"},
            "finished_contract": {"value_selection": "Yes"},
            "separation_reason": {"value_selection": "Own request"},
            "general_remarks": {"value_text": "Fictional background inquiry cleared for demonstration."},
        })
        orientation = self._sedar_record("sedar.document.request", "request_orientation_%s" % applicant.sedar_reference.lower().replace("-", "_"), {
            "name": "CM-053 Company Orientation - %s" % applicant.sedar_reference,
            "document_type_id": self.env.ref("sedar_document_control.document_type_cm_053").id,
            "subject_name": applicant.partner_name,
            "subject_reference": applicant.sedar_reference,
            "assigned_user_id": hr_manager.id,
            "due_date": "2026-08-24",
            "state": "draft",
            "applicant_id": applicant.id,
            "sedar_request_purpose": "orientation",
            "applicant_visible": False,
            "notes": "Fictional CM-053 orientation control managed by sedar_recruitment_demo.",
        })
        self._fill_document_request(orientation, {
            "orientation_date": {"value_date": "2026-08-22"},
            "applicant_name": {"value_text": applicant.partner_name},
            "position_applied": {"value_text": applicant.sedar_vacancy_id.website_title},
            "orientation_checklist": {"value_text": "ISM / ISO Orientation: Yes\nMission/Vision/Quality Policy: Yes\nJob Description: Yes\nCompany Rules & Regulation: Yes\nDisciplinary Action: Yes\nDrug-Free Workplace: Yes\nDuties & Responsibilities: Yes\nSafety On Board (Operation/Maintenance/Emergency): Yes"},
        })
        for request in background | orientation:
            if request.state != state:
                request.write({"state": state})
        return background | orientation

    def _sedar_demo_portal_owner(self):
        applicant = self.env.ref("%s.applicant_pending_requirements" % MODULE, raise_if_not_found=False)
        if not applicant:
            return
        partner = self._sedar_record("res.partner", "partner_applicant_portal", {
            "name": "Demo Applicant Portal User",
            "email": "applicant@sedar.demo",
        })
        user = self._sedar_record("res.users", "user_applicant_portal", {
            "name": "Demo Applicant Portal User",
            "login": "applicant@sedar.demo",
            "password": "applicantdemo",
            "partner_id": partner.id,
            "company_id": self.env.company.id,
            "company_ids": [Command.set([self.env.company.id])],
            "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
        })
        partner = user.partner_id
        applicant.write({
            "sedar_portal_partner_id": partner.id,
            "sedar_portal_claimed_at": _dt(18, 10),
            "sedar_claim_token": False,
        })

    def _fill_document_request(self, request, values):
        for value in request.value_ids:
            update = values.get(value.field_id.technical_name)
            if update:
                value.write(update)

    def _sedar_prune_duplicate_portal_events(self, applicant):
        seen = set()
        for event in applicant.sedar_portal_event_ids.sorted("id"):
            key = (event.event_type, event.title, event.message or "", event.visible)
            if key in seen:
                event.unlink()
            else:
                seen.add(key)

    def _sedar_record(self, model, xmlid, values):
        data = self.env["ir.model.data"].search([
            ("module", "=", MODULE),
            ("name", "=", xmlid),
        ], limit=1)
        if data:
            record = self.env[model].browse(data.res_id).exists()
            if record:
                managed = self._sedar_managed_values(record, values)
                if managed:
                    record.write(managed)
                return record
            data.unlink()
        record = self.env[model].create(values)
        self.env["ir.model.data"].create({
            "module": MODULE,
            "name": xmlid,
            "model": model,
            "res_id": record.id,
            "noupdate": True,
        })
        return record

    def _sedar_managed_values(self, record, values):
        managed = dict(values)
        if record._name == "res.users":
            managed.pop("password", None)
        if record._name == "hr.applicant":
            managed.pop("stage_id", None)
            managed.pop("sedar_public_status", None)
            managed.pop("sedar_rejection_reason", None)
            managed.pop("sedar_withdrawal_reason", None)
        if record._name == "sedar.document.request" and record.state not in ("draft", "in_progress"):
            managed.pop("state", None)
        if record._name == "sedar.document.request":
            managed.pop("document_type_id", None)
            managed.pop("applicant_id", None)
            managed.pop("sedar_request_purpose", None)
        if record._name in {"sedar.applicant.profile", "sedar.applicant.education", "sedar.applicant.employment"}:
            managed.pop("applicant_id", None)
        if record._name == "sedar.applicant.document":
            managed.pop("applicant_id", None)
            managed.pop("attachment_id", None)
        return managed

import base64
from datetime import date

from odoo import fields, http, tools
from odoo.http import request


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def _date(value):
    return fields.Date.to_date(value) if value else False


class SedarApplicantController(http.Controller):
    @http.route("/careers/apply/<string:slug>", type="http", auth="public", methods=["GET", "POST"], website=True)
    def apply(self, slug, **post):
        vacancy = request.env["sedar.job.vacancy"].sudo().search([("public_slug", "=", slug)], limit=1)
        if not vacancy or not vacancy.accepting_applications:
            return request.not_found()

        if request.httprequest.method == "POST":
            errors = self._validate(post, request.httprequest.files)
            if errors:
                return request.render("sedar_applicant_intake.application_form", self._context(vacancy, post, errors))
            applicant = self._create_application(vacancy, post, request.httprequest.files)
            return request.render("sedar_applicant_intake.application_submitted", {
                "reference": applicant.sedar_reference,
                "status_url": "/careers/application/status/%s" % applicant.sedar_tracking_token,
            })

        return request.render("sedar_applicant_intake.application_form", self._context(vacancy, {}, []))

    @http.route("/careers/application/status/<string:token>", type="http", auth="public", methods=["GET"], website=True)
    def status(self, token):
        applicant = request.env["hr.applicant"].sudo().search([("sedar_tracking_token", "=", token)], limit=1)
        if not applicant:
            return request.not_found()
        return request.render("sedar_applicant_intake.application_status", {
            "applicant": applicant,
            "reference": applicant.sedar_reference,
            "status": applicant.sedar_intake_state,
            "vacancy": applicant.sedar_vacancy_id,
        })

    @staticmethod
    def _context(vacancy, post, errors):
        return {"vacancy": vacancy, "form": post, "errors": errors, "today": date.today().isoformat()}

    @staticmethod
    def _validate(post, files):
        errors = []
        for field, label in (("family_name", "Family Name"), ("given_name", "Given Name"), ("email", "Email"), ("mobile", "Mobile Number")):
            if not (post.get(field) or "").strip():
                errors.append("%s is required." % label)
        email = (post.get("email") or "").strip()
        if email and not tools.single_email_re.match(email):
            errors.append("Enter a valid email address.")
        if not post.get("consent"):
            errors.append("Privacy consent is required before submission.")
        resume = files.get("resume")
        if not resume or not resume.filename:
            errors.append("A resume or CV is required.")
        for uploaded in files.values():
            if not uploaded or not uploaded.filename:
                continue
            extension = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
            if extension not in ALLOWED_EXTENSIONS:
                errors.append("%s has an unsupported file type." % uploaded.filename)
            uploaded.seek(0, 2)
            if uploaded.tell() > MAX_FILE_SIZE:
                errors.append("%s exceeds the 10 MB file limit." % uploaded.filename)
            uploaded.seek(0)
        return errors

    def _create_application(self, vacancy, post, files):
        email = (post.get("email") or "").strip()
        mobile = (post.get("mobile") or "").strip()
        duplicate = request.env["hr.applicant"].sudo().search([
            "|", ("email_from", "ilike", email), ("partner_phone", "=", mobile),
        ], limit=1) if email or mobile else False
        source = request.env["sedar.document.type"].sudo().search([("code", "=", "ADM-3")], limit=1)
        full_name = " ".join(part for part in (post.get("given_name"), post.get("middle_name"), post.get("family_name")) if part)
        applicant = request.env["hr.applicant"].sudo().create({
            "partner_name": full_name,
            "email_from": email,
            "partner_phone": mobile,
            "job_id": vacancy.job_id.id,
            "department_id": vacancy.department_id.id,
            "company_id": vacancy.department_id.company_id.id if vacancy.department_id.company_id else request.env.company.id,
            "sedar_vacancy_id": vacancy.id,
            "sedar_intake_state": "submitted",
            "sedar_document_type_id": source.id if source else False,
            "sedar_document_revision": (source.revision if source and source.revision else "Current approved ADM-3"),
            "sedar_consent": True,
            "sedar_consent_at": fields.Datetime.now(),
            "sedar_duplicate_warning": bool(duplicate),
        })
        profile = request.env["sedar.applicant.profile"].sudo().create({
            "applicant_id": applicant.id,
            "family_name": post.get("family_name"),
            "given_name": post.get("given_name"),
            "middle_name": post.get("middle_name"),
            "fathers_name": post.get("fathers_name"),
            "date_of_birth": _date(post.get("date_of_birth")),
            "place_of_birth": post.get("place_of_birth"),
            "age": int(post.get("age")) if (post.get("age") or "").isdigit() else False,
            "height": float(post.get("height")) if post.get("height") else False,
            "weight": float(post.get("weight")) if post.get("weight") else False,
            "civil_status": post.get("civil_status") or False,
            "contact_information": post.get("contact_information"),
            "identity_documents": post.get("identity_documents"),
            "skills": post.get("skills"),
            "training_entries": post.get("training_entries"),
            "medical_entries": post.get("medical_entries"),
            "emergency_contact": post.get("emergency_contact"),
            "certification_date": _date(post.get("certification_date")),
            "electronic_signature": post.get("electronic_signature"),
            "signature_date": fields.Date.context_today(applicant),
        })
        applicant.sedar_profile_id = profile.id
        self._create_lines(applicant, post)
        self._create_documents(applicant, files)
        applicant.message_post(body="Applicant submitted ADM-3 through the SEDAR Careers website.")
        return applicant

    @staticmethod
    def _create_lines(applicant, post):
        for index in range(1, 4):
            school = (post.get("education_school_%s" % index) or "").strip()
            if school:
                request.env["sedar.applicant.education"].sudo().create({
                    "applicant_id": applicant.id,
                    "school_name": school,
                    "course_name": post.get("education_course_%s" % index),
                    "date_from": _date(post.get("education_from_%s" % index)),
                    "date_to": _date(post.get("education_to_%s" % index)),
                    "english_knowledge": post.get("education_english_%s" % index),
                })
        for index in range(1, 4):
            company = (post.get("employment_company_%s" % index) or "").strip()
            if company:
                request.env["sedar.applicant.employment"].sudo().create({
                    "applicant_id": applicant.id,
                    "company_address": company,
                    "position": post.get("employment_position_%s" % index),
                    "date_from": _date(post.get("employment_from_%s" % index)),
                    "date_to": _date(post.get("employment_to_%s" % index)),
                    "reason_for_leaving": post.get("employment_reason_%s" % index),
                })

    @staticmethod
    def _create_documents(applicant, files):
        categories = {"resume": "resume", "photo": "photo", "cover_letter": "cover_letter"}
        uploads = [(name, upload, categories.get(name, "other")) for name, upload in files.items()]
        uploads = [(name, upload, category) for name, upload, category in uploads if upload and upload.filename]
        for name, upload, category in uploads:
            data = base64.b64encode(upload.read())
            attachment = request.env["ir.attachment"].sudo().create({
                "name": upload.filename,
                "datas": data,
                "res_model": "hr.applicant",
                "res_id": applicant.id,
                "mimetype": upload.content_type,
                "public": False,
            })
            request.env["sedar.applicant.document"].sudo().create({
                "applicant_id": applicant.id,
                "attachment_id": attachment.id,
                "category": category,
            })

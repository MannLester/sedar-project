import base64

from odoo import http
from odoo.http import request


class SedarRecruitmentInterviewPortal(http.Controller):
    def _owned_employee(self):
        partner = request.env.user.partner_id
        if not partner or request.env.user._is_public():
            return request.env["hr.employee"].sudo().browse()
        return request.env["hr.employee"].sudo().search([
            ("work_contact_id", "=", partner.id),
            ("active", "=", True),
        ], limit=1)

    @http.route("/my/sedar/employee", type="http", auth="user", website=True)
    def employee_dashboard(self):
        employee = self._owned_employee()
        if not employee:
            return request.not_found()
        applications = request.env["hr.applicant"].sudo().search([
            ("employee_id", "=", employee.id),
            ("sedar_portal_partner_id", "=", request.env.user.partner_id.id),
        ], order="create_date desc, id desc")
        documents = request.env["sedar.document.request"].sudo().search([
            ("applicant_id", "in", applications.ids),
        ], order="create_date desc, id desc")
        return request.render("sedar_recruitment_operations.employee_dashboard", {
            "employee": employee,
            "applications": applications,
            "documents": documents,
        })

    def _owned_interview(self, interview_id):
        partner = request.env.user.partner_id
        if not partner or request.env.user._is_public():
            return request.env["sedar.applicant.interview"].sudo().browse()
        return request.env["sedar.applicant.interview"].sudo().search([
            ("id", "=", interview_id),
            ("applicant_id.sedar_portal_partner_id", "=", partner.id),
            ("applicant_id.active", "=", True),
        ], limit=1)

    @http.route("/my/sedar/interviews/<int:interview_id>/confirm", type="http", auth="user", website=True, methods=["POST"])
    def confirm_interview(self, interview_id, **post):
        interview = self._owned_interview(interview_id)
        if not interview or interview.status not in ("scheduled", "reschedule"):
            return request.not_found()
        note = (post.get("confirmation_note") or "").strip()
        values = {"status": "confirmed", "applicant_confirmation_note": note or "Confirmed by applicant."}
        interview.write(values)
        interview.applicant_id._create_portal_event(
            "interview",
            "Interview Confirmed",
            "You confirmed your attendance for the scheduled interview.",
        )
        return request.redirect("/my/sedar/applications/%s" % interview.applicant_id.sedar_reference)

    def _owned_document_request(self, document_request_id):
        partner = request.env.user.partner_id
        if not partner or request.env.user._is_public():
            return request.env["sedar.document.request"].sudo().browse()
        return request.env["sedar.document.request"].sudo().search([
            ("id", "=", document_request_id),
            ("applicant_visible", "=", True),
            ("applicant_id.sedar_portal_partner_id", "=", partner.id),
            ("applicant_id.active", "=", True),
        ], limit=1)

    @http.route("/my/sedar/document-requests/<int:document_request_id>/submit", type="http", auth="user", website=True, methods=["POST"])
    def submit_document_request(self, document_request_id, **post):
        document_request = self._owned_document_request(document_request_id)
        if not document_request or document_request.state not in ("draft", "in_progress", "rejected"):
            return request.not_found()

        files = request.httprequest.files
        for value in document_request.value_ids:
            input_name = "value_%s" % value.id
            if value.field_type == "text" and input_name in post:
                value.write({"value_text": post.get(input_name)})
            elif value.field_type == "date" and post.get(input_name):
                value.write({"value_date": post.get(input_name)})
            elif value.field_type == "selection" and input_name in post:
                value.write({"value_selection": post.get(input_name)})
            elif value.field_type == "attachment":
                upload = files.get(input_name)
                if upload and upload.filename:
                    value.write({
                        "value_binary": base64.b64encode(upload.read()),
                        "value_filename": upload.filename,
                    })

        note = (post.get("applicant_submission_note") or "").strip()
        if note:
            document_request.write({"applicant_submission_note": note})
        if document_request.state == "draft":
            document_request.action_start()
        document_request.action_submit()
        document_request.applicant_id._move_to_sedar_stage(
            "sedar_recruitment_operations.stage_requirements_submitted",
            next_action="Review applicant employment requirements",
            message="Your employment requirements were submitted and are being reviewed by SEDAR HR.",
        )
        document_request.applicant_id._create_portal_event(
            "final_review",
            "Employment Requirements Submitted",
            "Your employment requirements were submitted to SEDAR HR.",
        )
        return request.redirect("/my/sedar/applications/%s" % document_request.applicant_id.sedar_reference)

    @http.route("/my/sedar/interviews/<int:interview_id>/reschedule", type="http", auth="user", website=True, methods=["POST"])
    def request_reschedule(self, interview_id, **post):
        interview = self._owned_interview(interview_id)
        if not interview or interview.status not in ("scheduled", "confirmed"):
            return request.not_found()
        reason = (post.get("reschedule_reason") or "").strip()
        interview.write({
            "status": "reschedule",
            "applicant_confirmation_note": reason or "Applicant requested a new interview schedule.",
        })
        interview.applicant_id._create_portal_event(
            "interview",
            "Interview Reschedule Requested",
            reason or "Your request for a new interview schedule has been sent to HR.",
        )
        return request.redirect("/my/sedar/applications/%s" % interview.applicant_id.sedar_reference)

import base64
from urllib.parse import quote

from odoo import fields, http
from odoo.http import request


STATUS_LABELS = {
    "received": "Application Received",
    "under_review": "Under Review",
    "shortlisted": "Shortlisted",
    "interview": "Interview Stage",
    "requirements": "Additional Requirements Needed",
    "final_review": "Final Review",
    "offer": "Offer Stage",
    "successful": "Application Successful",
    "closed": "Application Closed",
}


class SedarApplicantPortalController(http.Controller):
    @http.route("/careers/application/activate/<string:token>", type="http", auth="public", methods=["GET", "POST"], website=True)
    def activate(self, token, **post):
        applicant = request.env["hr.applicant"].sudo().search([("sedar_claim_token", "=", token)], limit=1)
        expired = not applicant or not applicant.sedar_claim_expires_at or applicant.sedar_claim_expires_at < fields.Datetime.now()
        if expired:
            return request.render("sedar_applicant_portal.activation_expired", {})
        if request.httprequest.method == "POST":
            password = post.get("password") or ""
            confirmation = post.get("password_confirmation") or ""
            errors = []
            if len(password) < 8:
                errors.append("Password must contain at least 8 characters.")
            if password != confirmation:
                errors.append("Password confirmation does not match.")
            if errors:
                return request.render("sedar_applicant_portal.activation_form", {"applicant": applicant, "errors": errors})
            try:
                self._activate_account(applicant, password)
            except ValueError as error:
                return request.render("sedar_applicant_portal.activation_form", {
                    "applicant": applicant,
                    "errors": [str(error)],
                })
            return request.render("sedar_applicant_portal.activation_complete", {"login": applicant.partner_id.email or applicant.email_from})
        return request.render("sedar_applicant_portal.activation_form", {"applicant": applicant, "errors": []})

    @http.route(["/my/sedar", "/my/sedar/applications"], type="http", auth="user", website=True)
    def dashboard(self):
        applications = self._owned_applications()
        return request.render("sedar_applicant_portal.dashboard", {"applications": applications})

    @http.route("/my/sedar/applications/<string:reference>", type="http", auth="user", website=True)
    def application(self, reference):
        applicant = self._owned_applications().filtered(lambda record: record.sedar_reference == reference)[:1]
        if not applicant:
            return request.not_found()
        return request.render("sedar_applicant_portal.application_detail", {
            "applicant": applicant,
            "status_label": STATUS_LABELS.get(applicant.sedar_public_status, applicant.sedar_public_status),
        })

    @http.route("/my/sedar/documents/<int:document_id>/download", type="http", auth="user", website=True)
    def download_document(self, document_id):
        document = request.env["sedar.applicant.document"].sudo().browse(document_id).exists()
        if not document or document.applicant_id not in self._owned_applications():
            return request.not_found()
        attachment = document.attachment_id
        if not attachment.datas:
            return request.not_found()
        filename = quote(attachment.name or "document", safe="")
        return request.make_response(
            base64.b64decode(attachment.datas),
            headers=[
                ("Content-Type", attachment.mimetype or "application/octet-stream"),
                ("Content-Disposition", "attachment; filename*=UTF-8''%s" % filename),
            ],
        )

    @staticmethod
    def _activate_account(applicant, password):
        partner = applicant.partner_id.sudo()
        portal_group = request.env.ref("base.group_portal")
        user = partner.user_ids[:1].sudo()
        if user and not user.share:
            raise ValueError("This contact already has an internal user account.")
        if not user:
            user = request.env["res.users"].sudo().with_context(no_reset_password=True).create({
                "name": partner.name,
                "login": partner.email or applicant.email_from,
                "email": partner.email or applicant.email_from,
                "partner_id": partner.id,
                "password": password,
                "group_ids": [(6, 0, [portal_group.id])],
            })
        else:
            user.write({"active": True, "password": password, "group_ids": [(4, portal_group.id)]})
        applicants = request.env["hr.applicant"].sudo().search([
            "|", ("id", "=", applicant.id), ("partner_id", "=", partner.id),
        ])
        applicants.write({
            "sedar_portal_partner_id": partner.id,
            "sedar_portal_claimed_at": fields.Datetime.now(),
            "sedar_claim_token": False,
            "sedar_claim_expires_at": False,
        })

    def _owned_applications(self):
        partner = request.env.user.partner_id
        if not partner or request.env.user._is_public():
            return request.env["hr.applicant"].sudo().browse()
        return request.env["hr.applicant"].sudo().search([
            ("sedar_portal_partner_id", "=", partner.id),
            ("active", "=", True),
        ], order="create_date desc, id desc")

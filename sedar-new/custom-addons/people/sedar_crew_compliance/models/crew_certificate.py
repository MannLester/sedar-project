from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class SedarCrewCertificate(models.Model):
    _inherit = "sedar.crew.certificate"

    sedar_document_request_id = fields.Many2one(
        "sedar.document.request",
        string="Controlled Evidence Request",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    sedar_verification_state = fields.Selection(
        [
            ("verified", "Verified"),
            ("requested", "Renewal Requested"),
            ("submitted", "Submitted for Review"),
            ("rejected", "Rejected"),
        ],
        string="Evidence Status",
        required=True,
        default="verified",
        copy=False,
    )
    sedar_verified_by_id = fields.Many2one("res.users", string="Verified By", readonly=True, copy=False)
    sedar_verified_at = fields.Datetime(string="Verified At", readonly=True, copy=False)
    sedar_renewal_requested_by_id = fields.Many2one(
        "res.users", string="Renewal Requested By", readonly=True, copy=False
    )
    sedar_renewal_requested_at = fields.Datetime(string="Renewal Requested At", readonly=True, copy=False)
    sedar_renewal_due_date = fields.Date(
        string="Renewal Due Date", compute="_compute_sedar_expiry_controls", store=True
    )
    sedar_expiry_state = fields.Selection(
        [
            ("valid", "Valid"),
            ("renewal_due", "Renewal Due"),
            ("expired", "Expired"),
        ],
        string="Expiry Control",
        compute="_compute_sedar_expiry_controls",
        store=True,
    )
    sedar_is_medical = fields.Boolean(
        string="Medical Record",
        compute="_compute_sedar_is_medical",
        store=True,
    )
    sedar_reviewer_note = fields.Text(string="Compliance Reviewer Note", copy=False)

    @api.depends("expiry_date")
    def _compute_sedar_expiry_controls(self):
        today = fields.Date.context_today(self)
        warning_date = fields.Date.add(today, days=30)
        for certificate in self:
            certificate.sedar_renewal_due_date = fields.Date.subtract(certificate.expiry_date, days=30)
            if certificate.expiry_date < today:
                certificate.sedar_expiry_state = "expired"
            elif certificate.expiry_date <= warning_date:
                certificate.sedar_expiry_state = "renewal_due"
            else:
                certificate.sedar_expiry_state = "valid"

    @api.depends("certificate_type_id.code", "certificate_type_id.name")
    def _compute_sedar_is_medical(self):
        for certificate in self:
            code = (certificate.certificate_type_id.code or "").upper()
            name = (certificate.certificate_type_id.name or "").upper()
            certificate.sedar_is_medical = "MED" in code or "MEDICAL" in name

    def action_sedar_request_renewal(self):
        self._ensure_compliance_manager()
        document_type = self.env.ref("sedar_crew_compliance.document_type_crew_credential_evidence")
        for certificate in self:
            request = certificate.sedar_document_request_id
            if not request:
                profile = certificate.crew_profile_id.sudo()
                employee = profile.employee_id.sudo()
                request = self.env["sedar.document.request"].create({
                    "name": "Credential Renewal - %s - %s" % (
                        employee.name,
                        certificate.certificate_type_id.name,
                    ),
                    "document_type_id": document_type.id,
                    "subject_name": employee.name,
                    "subject_reference": profile.employee_number,
                    "assigned_user_id": self.env.user.id,
                    "due_date": certificate.sedar_renewal_due_date or fields.Date.context_today(self),
                    "notes": "Upload controlled evidence for the crew credential or medical renewal.",
                })
                certificate._sedar_prefill_request_values(request)
            certificate.write({
                "sedar_document_request_id": request.id,
                "sedar_verification_state": "requested",
                "sedar_renewal_requested_by_id": self.env.user.id,
                "sedar_renewal_requested_at": fields.Datetime.now(),
            })
            if request.state == "draft":
                request.action_start()
        return True

    def action_sedar_sync_from_document(self):
        self._ensure_compliance_manager()
        for certificate in self:
            request = certificate.sedar_document_request_id
            if not request:
                raise UserError("Create a controlled evidence request before syncing evidence.")
            certificate._sedar_apply_request_values(request)
            if request.state in {"draft", "in_progress"}:
                certificate.sedar_verification_state = "requested"
            elif request.state in {"submitted", "reviewed"}:
                certificate.sedar_verification_state = "submitted"
            elif request.state == "rejected":
                certificate.sedar_verification_state = "rejected"
            elif request.state == "approved":
                certificate._sedar_mark_verified()
        return True

    def action_sedar_verify(self):
        self._ensure_compliance_manager()
        for certificate in self:
            request = certificate.sedar_document_request_id
            if not request or request.state != "approved":
                raise UserError("Approve the controlled evidence request before verifying this credential.")
            certificate._sedar_apply_request_values(request)
            certificate._sedar_mark_verified()
        return True

    def action_sedar_reject(self):
        self._ensure_compliance_manager()
        for certificate in self:
            if not certificate.sedar_reviewer_note:
                raise UserError("Enter a reviewer note before rejecting evidence.")
            certificate.sedar_verification_state = "rejected"
        return True

    def action_sedar_open_document_request(self):
        self.ensure_one()
        if not self.sedar_document_request_id:
            raise UserError("No controlled evidence request is linked to this credential.")
        return {
            "type": "ir.actions.act_window",
            "name": "Controlled Evidence Request",
            "res_model": "sedar.document.request",
            "res_id": self.sedar_document_request_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _sedar_prefill_request_values(self, request):
        self.ensure_one()
        profile = self.crew_profile_id.sudo()
        values_by_name = {
            "crew_profile": profile.display_name,
            "certificate_type": self.certificate_type_id.name,
            "certificate_number": self.certificate_number,
            "issue_date": self.issue_date,
            "expiry_date": self.expiry_date,
        }
        for value in request.value_ids:
            current = values_by_name.get(value.field_id.technical_name)
            if value.field_type == "date":
                value.value_date = current
            elif value.field_type == "text" and current:
                value.value_text = current

    def _sedar_apply_request_values(self, request):
        self.ensure_one()
        vals = {}
        for value in request.value_ids:
            technical_name = value.field_id.technical_name
            if technical_name == "certificate_number" and value.value_text:
                vals["certificate_number"] = value.value_text
            elif technical_name == "issue_date" and value.value_date:
                vals["issue_date"] = value.value_date
            elif technical_name == "expiry_date" and value.value_date:
                vals["expiry_date"] = value.value_date
            elif technical_name == "reviewer_notes" and value.value_text:
                vals["sedar_reviewer_note"] = value.value_text
        if vals:
            self.with_context(sedar_compliance_action=True).write(vals)

    def _sedar_mark_verified(self):
        today = fields.Date.context_today(self)
        if self.expiry_date < today:
            raise UserError("An expired crew credential or medical record cannot be verified.")
        self.with_context(sedar_compliance_action=True).write({
            "sedar_verification_state": "verified",
            "sedar_verified_by_id": self.env.user.id,
            "sedar_verified_at": fields.Datetime.now(),
        })

    def _ensure_compliance_manager(self):
        if not self.env.user.has_group("sedar_crew_compliance.group_crew_compliance_manager"):
            raise AccessError("Only a Crew Compliance Manager may control crew credential evidence.")
        return True

    def write(self, vals):
        protected = {
            "sedar_document_request_id",
            "sedar_verification_state",
            "sedar_verified_by_id",
            "sedar_verified_at",
            "sedar_renewal_requested_by_id",
            "sedar_renewal_requested_at",
        }
        if protected.intersection(vals) and not self.env.context.get("sedar_compliance_action"):
            self._ensure_compliance_manager()
        return super().write(vals)

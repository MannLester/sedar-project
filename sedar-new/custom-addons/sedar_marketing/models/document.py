from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


DOCUMENT_TYPES = [
    ("contract", "Contract"), ("quotation", "Quotation"), ("invoice", "Invoice"),
    ("purchase_order", "Purchase Order"), ("service_report", "Service Report"),
    ("certificate", "Certificate"), ("insurance", "Insurance"),
    ("correspondence", "Correspondence"), ("marketing_material", "Marketing Material"),
    ("other", "Other"),
]
DEPARTMENTS = [
    ("marketing", "Marketing"), ("operations", "Operations"), ("finance", "Finance"),
    ("document_control", "Document Control"), ("hsse", "HSSE"),
    ("technical", "Technical"), ("management", "Management"),
]


class SedarMarketingDocument(models.Model):
    _name = "sedar.marketing.document"
    _description = "SEDAR Customer Document Metadata"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "updated_at desc, id desc"

    name = fields.Char(string="Document", default="New", readonly=True, copy=False, index=True)
    customer_id = fields.Many2one("res.partner", required=True, index=True, ondelete="cascade")
    title = fields.Char(required=True, tracking=True)
    description = fields.Text()
    document_type = fields.Selection(DOCUMENT_TYPES, required=True, tracking=True)
    department = fields.Selection(DEPARTMENTS, required=True, default="marketing", tracking=True)
    visibility = fields.Selection(
        [("internal", "Marketing Only"), ("shared", "Shared")],
        default="internal", required=True, tracking=True
    )
    source = fields.Selection(
        [("uploaded", "Marketing Upload Record"), ("official", "Official Record")],
        default="uploaded", required=True, readonly=True
    )
    status = fields.Selection([
        ("active", "Active"), ("expired", "Expired"), ("archived", "Archived")
    ], default="active", required=True, tracking=True, index=True)
    expiry_date = fields.Date(tracking=True)
    linked_service_order_id = fields.Many2one("sedar.marine.service.order", string="Service Request", ondelete="set null")
    linked_quotation_id = fields.Many2one("sedar.marketing.quotation", ondelete="set null")
    linked_contract_id = fields.Many2one("sedar.marketing.contract", ondelete="set null")
    linked_invoice_id = fields.Many2one("account.move", string="Invoice", ondelete="set null")
    linked_appointment_id = fields.Many2one("calendar.event", string="Appointment", ondelete="set null")
    official_document_id = fields.Many2one("sedar.document", readonly=True, ondelete="restrict")
    version_ids = fields.One2many("sedar.marketing.document.version", "document_id", string="Versions", copy=True)
    current_version = fields.Integer(compute="_compute_current_version", store=True)
    created_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    updated_at = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    archived_at = fields.Datetime(readonly=True, copy=False)
    archived_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    is_marketing_editable = fields.Boolean(compute="_compute_is_marketing_editable")

    _name_unique = models.Constraint("UNIQUE(name)", "Customer document reference must be unique.")

    @api.depends("version_ids.version")
    def _compute_current_version(self):
        for document in self:
            document.current_version = max(document.version_ids.mapped("version"), default=0)

    @api.depends("department", "source", "status")
    def _compute_is_marketing_editable(self):
        for document in self:
            document.is_marketing_editable = (
                document.department == "marketing"
                and document.source == "uploaded"
                and document.status != "archived"
            )

    def _check_marketing_owner(self, allow_archived=False):
        if self.env.su or self.env.context.get("sedar_official_document_sync"):
            return
        if any(item.department != "marketing" or item.source != "uploaded" for item in self):
            raise AccessError("Official and other-department document records are read-only in Marketing.")
        if not allow_archived and any(item.status == "archived" for item in self):
            raise AccessError("Archived document records must be restored before editing.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.context.get("sedar_official_document_sync"):
            if any(vals.get("department", "marketing") != "marketing" or vals.get("source", "uploaded") != "uploaded" for vals in vals_list):
                raise AccessError("Marketing users may create only Marketing-owned upload records.")
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("sedar.marketing.document") or "New"
        documents = super().create(vals_list)
        for document in documents:
            self.env["sedar.marketing.activity"].log(
                document.customer_id, "documents", "uploaded" if document.source == "uploaded" else "created",
                f"Document record {document.name} registered.", document,
            )
        return documents

    def write(self, vals):
        self._check_marketing_owner(allow_archived=vals.keys() <= {"status", "archived_at", "archived_by_id", "updated_at"})
        vals = dict(vals, updated_at=fields.Datetime.now())
        result = super().write(vals)
        if not self.env.context.get("sedar_skip_document_log"):
            for document in self:
                action = "archived" if vals.get("status") == "archived" else "updated"
                self.env["sedar.marketing.activity"].log(
                    document.customer_id, "documents", action,
                    f"Document record {document.name} updated.", document,
                )
        return result

    def unlink(self):
        self._check_marketing_owner(allow_archived=True)
        if any(item.status != "archived" for item in self):
            raise AccessError("Only archived Marketing-owned document records may be deleted.")
        return super().unlink()

    def action_archive(self):
        self._check_marketing_owner()
        self.write({
            "status": "archived", "archived_at": fields.Datetime.now(),
            "archived_by_id": self.env.user.id,
        })

    def action_restore(self):
        self._check_marketing_owner(allow_archived=True)
        self.write({"status": "active", "archived_at": False, "archived_by_id": False})


class SedarMarketingDocumentVersion(models.Model):
    _name = "sedar.marketing.document.version"
    _description = "SEDAR Customer Document Version Metadata"
    _order = "version desc, id desc"

    document_id = fields.Many2one("sedar.marketing.document", required=True, ondelete="cascade", index=True)
    version = fields.Integer(readonly=True, copy=False)
    filename = fields.Char(required=True)
    mime_type = fields.Char(required=True)
    size_bytes = fields.Integer(required=True)
    uploaded_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    uploaded_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    notes = fields.Text()

    _document_version_unique = models.Constraint(
        "UNIQUE(document_id, version)", "Document version numbers must be unique."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            document = self.env["sedar.marketing.document"].browse(vals["document_id"])
            document._check_marketing_owner()
            vals["version"] = max(document.version_ids.mapped("version"), default=0) + 1
            if vals.get("size_bytes", 0) < 0 or vals.get("size_bytes", 0) > 25 * 1024 * 1024:
                raise ValidationError("Document version size must be between 0 and 25 MB.")
        versions = super().create(vals_list)
        for version in versions:
            version.document_id.with_context(sedar_skip_document_log=True).write({"updated_at": fields.Datetime.now()})
            self.env["sedar.marketing.activity"].log(
                version.document_id.customer_id, "documents", "uploaded",
                f"Version {version.version} recorded for {version.document_id.name}.", version.document_id,
            )
        return versions

    def write(self, vals):
        raise AccessError("Document version history is immutable.")

    def unlink(self):
        raise AccessError("Document version history cannot be deleted.")


class SedarMarketingDocumentRequest(models.Model):
    _name = "sedar.marketing.document.request"
    _description = "SEDAR Customer Document Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "requested_at desc, id desc"

    name = fields.Char(string="Request", default="New", readonly=True, copy=False, index=True)
    customer_id = fields.Many2one("res.partner", required=True, index=True, ondelete="cascade")
    title = fields.Char(required=True)
    document_type = fields.Selection(DOCUMENT_TYPES, required=True)
    description = fields.Text()
    requested_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    requested_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    due_date = fields.Date()
    department = fields.Selection(DEPARTMENTS, required=True, default="marketing")
    status = fields.Selection([
        ("pending", "Pending"), ("fulfilled", "Fulfilled"), ("cancelled", "Cancelled")
    ], default="pending", required=True, tracking=True)
    fulfilled_document_id = fields.Many2one("sedar.marketing.document", readonly=True, ondelete="restrict")
    fulfilled_at = fields.Datetime(readonly=True)
    fulfilled_by_id = fields.Many2one("res.users", readonly=True)
    cancellation_reason = fields.Text()

    _name_unique = models.Constraint("UNIQUE(name)", "Document request reference must be unique.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("sedar.marketing.document.request") or "New"
        requests = super().create(vals_list)
        for request in requests:
            self.env["sedar.marketing.activity"].log(
                request.customer_id, "documents", "created",
                f"Document request {request.name} created.", request,
            )
        return requests

    def action_fulfill(self):
        if any(item.status != "pending" or not item.fulfilled_document_id for item in self):
            raise UserError("Select a document before fulfilling a pending request.")
        self.write({
            "status": "fulfilled", "fulfilled_at": fields.Datetime.now(),
            "fulfilled_by_id": self.env.user.id,
        })

    def action_cancel(self):
        if any(item.status != "pending" or not item.cancellation_reason for item in self):
            raise UserError("A cancellation reason is required for a pending request.")
        self.write({"status": "cancelled"})

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarDocumentType(models.Model):
    _name = "sedar.document.type"
    _description = "SEDAR Document Catalogue Entry"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    department = fields.Char()
    description = fields.Text()
    revision = fields.Char()
    effective_date = fields.Date()
    issue_number = fields.Char()
    source_filename = fields.Char()
    approval_status = fields.Selection(
        [("approved", "Approved"), ("draft", "Draft"), ("retired", "Retired")],
        default="draft", required=True,
    )
    field_definition = fields.Text(string="Approved Field Definition")
    field_ids = fields.One2many("sedar.document.field", "document_type_id", string="Typed Fields")
    document_ids = fields.One2many("sedar.document", "document_type_id")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Document code must be unique.")


class SedarDocument(models.Model):
    _name = "sedar.document"
    _description = "SEDAR Controlled Document"
    _order = "document_type_id, name"

    name = fields.Char(required=True)
    document_type_id = fields.Many2one("sedar.document.type", required=True, ondelete="restrict")
    file = fields.Binary(string="Source PDF", attachment=True, required=True)
    filename = fields.Char(required=True)
    state = fields.Selection(
        [("active", "Active"), ("superseded", "Superseded"), ("archived", "Archived")],
        default="active", required=True,
    )
    notes = fields.Text()


class SedarDocumentField(models.Model):
    _name = "sedar.document.field"
    _description = "SEDAR Typed Document Field"
    _order = "document_type_id, sequence, id"

    name = fields.Char(string="Field Label", required=True)
    technical_name = fields.Char(required=True, index=True)
    document_type_id = fields.Many2one("sedar.document.type", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    field_type = fields.Selection(
        [
            ("text", "Text"),
            ("date", "Date"),
            ("integer", "Whole Number"),
            ("decimal", "Decimal Number"),
            ("boolean", "Yes / No"),
            ("selection", "Selection"),
            ("attachment", "Attachment"),
            ("signature", "Signature"),
        ],
        required=True,
    )
    required = fields.Boolean(default=False)
    help_text = fields.Text(string="Instructions")
    selection_options = fields.Text(
        help="One option per line. Used when Field Type is Selection."
    )

    _technical_name_unique = models.Constraint(
        "UNIQUE(document_type_id, technical_name)",
        "Technical field name must be unique within a document template.",
    )


class SedarDocumentRequest(models.Model):
    _name = "sedar.document.request"
    _description = "SEDAR Employee or Applicant Document Request"
    _order = "create_date desc"

    name = fields.Char(required=True, default="New Document Request")
    document_type_id = fields.Many2one(
        "sedar.document.type", required=True, ondelete="restrict"
    )
    subject_name = fields.Char(string="Applicant / Employee", required=True)
    subject_reference = fields.Char(string="Employee / Applicant ID")
    assigned_user_id = fields.Many2one("res.users", string="Assigned HR User")
    due_date = fields.Date()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("submitted", "Submitted"),
            ("reviewed", "Reviewed"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()
    value_ids = fields.One2many("sedar.document.value", "request_id", string="Form Values")
    completion_percent = fields.Float(compute="_compute_completion", string="Completion %")

    def _template_value_commands(self):
        self.ensure_one()
        return [
            fields.Command.create({"field_id": field.id})
            for field in self.document_type_id.field_ids.sorted("sequence")
        ]

    @api.onchange("document_type_id")
    def _onchange_document_type_id(self):
        if self.document_type_id:
            self.value_ids = [fields.Command.clear(), *self._template_value_commands()]

    @api.depends("value_ids.is_completed")
    def _compute_completion(self):
        for request in self:
            total = len(request.value_ids)
            completed = len(request.value_ids.filtered("is_completed"))
            request.completion_percent = (completed / total * 100) if total else 0

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for request in requests:
            request.value_ids = request._template_value_commands()
        return requests

    def write(self, vals):
        result = super().write(vals)
        if "document_type_id" in vals:
            for request in self:
                request.value_ids = [fields.Command.clear(), *request._template_value_commands()]
        return result

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_submit(self):
        for request in self:
            missing = request.value_ids.filtered(lambda value: value.is_required and not value.is_completed)
            if missing:
                raise ValidationError(
                    "Complete the required fields before submitting: %s"
                    % ", ".join(missing.mapped("field_label"))
                )
        self.write({"state": "submitted"})

    def action_review(self):
        self.write({"state": "reviewed"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_reject(self):
        self.write({"state": "rejected"})


class SedarDocumentValue(models.Model):
    _name = "sedar.document.value"
    _description = "SEDAR Document Field Value"
    # Related fields cannot be used in a model-level SQL order in Odoo.
    _order = "id"

    request_id = fields.Many2one("sedar.document.request", required=True, ondelete="cascade")
    field_id = fields.Many2one("sedar.document.field", required=True, ondelete="restrict")
    field_type = fields.Selection(related="field_id.field_type", readonly=True)
    field_label = fields.Char(related="field_id.name", readonly=True)
    is_required = fields.Boolean(related="field_id.required", readonly=True)
    is_completed = fields.Boolean(compute="_compute_completed", store=True)
    value_text = fields.Text(string="Text Value")
    value_date = fields.Date(string="Date Value")
    value_integer = fields.Integer(string="Whole Number Value")
    value_decimal = fields.Float(string="Decimal Value")
    value_boolean = fields.Boolean(string="Yes / No Value")
    value_selection = fields.Char(string="Selected Option")
    value_binary = fields.Binary(string="Uploaded File", attachment=True)
    value_filename = fields.Char(string="Filename")
    value_signature = fields.Binary(string="Signature", attachment=True)
    comment = fields.Text(string="Reviewer Comment")

    _request_field_unique = models.Constraint(
        "UNIQUE(request_id, field_id)",
        "A document request can contain each template field only once.",
    )

    @api.depends(
        "field_type", "value_text", "value_date", "value_integer", "value_decimal",
        "value_boolean", "value_selection", "value_binary", "value_signature"
    )
    def _compute_completed(self):
        for value in self:
            if value.field_type == "boolean":
                value.is_completed = True
            elif value.field_type == "date":
                value.is_completed = bool(value.value_date)
            elif value.field_type == "integer":
                value.is_completed = value.value_integer is not False and value.value_integer is not None
            elif value.field_type == "decimal":
                value.is_completed = value.value_decimal is not False and value.value_decimal is not None
            elif value.field_type == "selection":
                value.is_completed = bool(value.value_selection)
            elif value.field_type == "attachment":
                value.is_completed = bool(value.value_binary)
            elif value.field_type == "signature":
                value.is_completed = bool(value.value_signature)
            else:
                value.is_completed = bool(value.value_text)

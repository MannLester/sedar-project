import re

from odoo import api, fields, models
from odoo.exceptions import AccessError


RESTRICTED_FIELD = re.compile(
    r"password|passcode|secret|token|authorization|cookie|session|api.?key|private.?key|"
    r"credit.?card|payment.?credential|card.?number|cvv|bank.?account|tax|tin|"
    r"sensitive.?identifier|signature.?image|portal.?credential|base64|blob|file.?content|finance.?note",
    re.I,
)
REDACTED_VALUE = "Restricted field updated"


class SedarMarketingActivity(models.Model):
    _name = "sedar.marketing.activity"
    _description = "SEDAR Marketing Activity Log"
    _order = "occurred_at desc, id desc"

    customer_id = fields.Many2one("res.partner", required=True, index=True, ondelete="cascade")
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    module = fields.Selection([
        ("customer", "Customer Account"), ("contacts", "Contacts"),
        ("service_requests", "Service Requests"), ("quotations", "Quotations"),
        ("contract_requests", "Contract Requests"), ("contracts", "Contracts"),
        ("appointments", "Appointments"), ("documents", "Documents"),
        ("finance", "Finance Summary"), ("system", "System"),
    ], required=True, index=True)
    action = fields.Selection([
        ("created", "Created"), ("updated", "Updated"), ("assigned", "Assigned"),
        ("status_changed", "Status Changed"), ("note_added", "Note Added"),
        ("contacted", "Contacted"), ("submitted", "Submitted"),
        ("approved", "Approved"), ("rejected", "Rejected"),
        ("cancelled", "Cancelled"), ("uploaded", "Uploaded"),
        ("downloaded", "Downloaded"), ("archived", "Archived"),
        ("followup_created", "Follow-up Created"),
        ("followup_completed", "Follow-up Completed"),
    ], required=True, index=True)
    description = fields.Char(required=True)
    actor_id = fields.Many2one("res.users", readonly=True, ondelete="set null")
    actor_name = fields.Char(required=True)
    actor_type = fields.Selection([
        ("employee", "SEDAR Employee"), ("department", "SEDAR Department"),
        ("customer", "Customer"), ("system", "System"),
    ], required=True, default="employee")
    actor_department = fields.Char()
    visibility = fields.Selection([
        ("internal", "Internal"), ("customer", "Customer-Originated"),
        ("restricted", "Restricted"),
    ], required=True, default="internal", index=True)
    related_model = fields.Char(index=True)
    related_record_id = fields.Integer(index=True)
    reference = fields.Char(index=True)
    change_summary = fields.Text(readonly=True)
    source_event_key = fields.Char(index=True, copy=False)
    system_generated = fields.Boolean(default=True, readonly=True)

    _source_event_key_unique = models.Constraint(
        "UNIQUE(source_event_key)", "An activity source event may only be recorded once."
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sedar_activity_write"):
            raise AccessError("The Marketing Activity Log is append-only and system-maintained.")
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError("Marketing Activity Log entries cannot be changed.")

    def unlink(self):
        raise AccessError("Marketing Activity Log entries cannot be deleted.")

    @api.model
    def _safe_change_summary(self, changes):
        lines = []
        for field_name, previous, current in changes or []:
            if RESTRICTED_FIELD.search(field_name or ""):
                lines.append(f"Restricted field: {REDACTED_VALUE}")
                continue
            previous = self._safe_value(previous)
            current = self._safe_value(current)
            lines.append(f"{field_name[:80]}: {previous} → {current}")
        return "\n".join(lines)

    @api.model
    def _safe_value(self, value):
        if value in (None, False):
            return "—"
        if isinstance(value, (int, float, bool)):
            return str(value)
        text = str(value)
        if "BEGIN PRIVATE KEY" in text.upper() or text.lower().startswith("bearer "):
            return REDACTED_VALUE
        return text[:500]

    @api.model
    def log(self, customer, module, action, description, record=None, changes=None,
            visibility="internal", actor=None, actor_type="employee", source_event_key=None):
        customer = customer.commercial_partner_id
        actor = actor or self.env.user
        values = {
            "customer_id": customer.id,
            "module": module,
            "action": action,
            "description": description,
            "actor_id": actor.id if actor and actor._name == "res.users" else False,
            "actor_name": actor.name if actor else "SEDAR System",
            "actor_type": actor_type,
            "actor_department": "Marketing" if actor_type == "employee" else False,
            "visibility": visibility,
            "related_model": record._name if record else False,
            "related_record_id": record.id if record else False,
            "reference": record.display_name if record else False,
            "change_summary": self._safe_change_summary(changes),
            "source_event_key": source_event_key,
        }
        if source_event_key and self.search_count([("source_event_key", "=", source_event_key)]):
            return self.browse()
        return self.sudo().with_context(sedar_activity_write=True).create(values)

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarMarketingContactType(models.Model):
    _name = "sedar.marketing.contact.type"
    _description = "SEDAR Marketing Contact Type"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Contact type code must be unique.")


class SedarMarketingAvailabilityDay(models.Model):
    _name = "sedar.marketing.availability.day"
    _description = "SEDAR Marketing Availability Day"
    _order = "sequence"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)

    _code_unique = models.Constraint("UNIQUE(code)", "Availability day code must be unique.")


class ResPartner(models.Model):
    _inherit = "res.partner"

    sedar_is_customer_account = fields.Boolean(string="SEDAR Customer Account", index=True, tracking=True)
    sedar_customer_code = fields.Char(string="Customer ID", copy=False, index=True, tracking=True)
    sedar_customer_type = fields.Selection([
        ("shipping_company", "Shipping Company"), ("vessel_owner", "Vessel Owner"),
        ("port_operator", "Port Operator"), ("maritime_agency", "Maritime Agency"),
        ("industrial_client", "Industrial Client"),
        ("government_agency", "Government Agency"),
    ], string="Customer Type", tracking=True)
    sedar_account_status = fields.Selection([
        ("prospect", "Prospect"), ("active", "Active"),
        ("inactive", "Inactive"), ("restricted", "Restricted"),
    ], string="Account Status", default="prospect", tracking=True)
    sedar_assigned_marketing_user_id = fields.Many2one(
        "res.users", string="Assigned Representative", tracking=True, ondelete="set null"
    )
    sedar_lead_source = fields.Char(string="Lead Source", tracking=True)
    sedar_customer_since = fields.Date(string="Customer Since", tracking=True)
    sedar_last_interaction_at = fields.Datetime(string="Last Interaction", tracking=True)
    sedar_next_follow_up_date = fields.Date(string="Next Follow-up Date", tracking=True)
    sedar_relationship_status = fields.Selection([
        ("new", "New"), ("developing", "Developing"),
        ("established", "Established"), ("at_risk", "At Risk"),
    ], default="new", tracking=True)
    sedar_primary_contact_id = fields.Many2one(
        "res.partner", string="Primary Contact", tracking=True, ondelete="set null"
    )

    sedar_contact_type_ids = fields.Many2many(
        "sedar.marketing.contact.type", "sedar_partner_contact_type_rel",
        "partner_id", "type_id", string="Contact Types"
    )
    sedar_contact_status = fields.Selection(
        [("active", "Active"), ("inactive", "Inactive")], default="active", tracking=True
    )
    sedar_preferred_contact_method = fields.Selection([
        ("email", "Email"), ("phone", "Phone"), ("sms", "SMS")
    ], default="email")
    sedar_availability_day_ids = fields.Many2many(
        "sedar.marketing.availability.day", "sedar_partner_availability_day_rel",
        "partner_id", "day_id", string="Available Days"
    )
    sedar_preferred_contact_start = fields.Float(string="Available From")
    sedar_preferred_contact_end = fields.Float(string="Available Until")
    sedar_can_approve_quotations = fields.Boolean(string="Can Approve Quotations")
    sedar_can_sign_contracts = fields.Boolean(string="Can Sign Contracts")
    sedar_can_coordinate_operations = fields.Boolean(string="Can Coordinate Operations")
    sedar_contact_internal_notes = fields.Text(string="Marketing Contact Notes")
    sedar_last_contacted_at = fields.Datetime(string="Last Contacted")
    sedar_is_primary_contact = fields.Boolean(compute="_compute_sedar_is_primary_contact")

    sedar_service_order_ids = fields.One2many(
        "sedar.marine.service.order", "client_id", string="Service Requests"
    )
    sedar_marketing_quotation_ids = fields.One2many(
        "sedar.marketing.quotation", "customer_id", string="Quotations"
    )
    sedar_marketing_contract_ids = fields.One2many(
        "sedar.marketing.contract", "customer_id", string="Contracts"
    )
    sedar_marketing_appointment_ids = fields.One2many(
        "calendar.event", "sedar_customer_id", string="Appointments"
    )
    sedar_marketing_document_ids = fields.One2many(
        "sedar.marketing.document", "customer_id", string="Documents"
    )
    sedar_marketing_document_request_ids = fields.One2many(
        "sedar.marketing.document.request", "customer_id", string="Document Requests"
    )
    sedar_marketing_activity_ids = fields.One2many(
        "sedar.marketing.activity", "customer_id", string="Activity Log"
    )
    sedar_marketing_note_ids = fields.One2many(
        "sedar.marketing.internal.note", "customer_id", string="Internal Notes"
    )
    sedar_marketing_transaction_ids = fields.One2many(
        "sedar.marketing.transaction", "customer_id", string="Transaction History"
    )
    sedar_total_service_request_count = fields.Integer(compute="_compute_sedar_marketing_counts")
    sedar_active_quotation_count = fields.Integer(compute="_compute_sedar_marketing_counts")
    sedar_active_contract_count = fields.Integer(compute="_compute_sedar_marketing_counts")
    sedar_completed_service_count = fields.Integer(compute="_compute_sedar_marketing_counts")

    _sedar_customer_code_unique = models.Constraint(
        "UNIQUE(sedar_customer_code)", "SEDAR Customer ID must be unique."
    )

    @api.depends("parent_id.sedar_primary_contact_id", "commercial_partner_id.sedar_primary_contact_id")
    def _compute_sedar_is_primary_contact(self):
        for partner in self:
            commercial = partner.commercial_partner_id
            partner.sedar_is_primary_contact = commercial.sedar_primary_contact_id == partner

    @api.depends(
        "sedar_service_order_ids.state", "sedar_marketing_quotation_ids.status",
        "sedar_marketing_contract_ids.status",
    )
    def _compute_sedar_marketing_counts(self):
        for customer in self:
            orders = customer.sedar_service_order_ids
            customer.sedar_total_service_request_count = len(orders)
            customer.sedar_active_quotation_count = len(customer.sedar_marketing_quotation_ids.filtered(
                lambda item: item.status not in {"rejected", "expired", "superseded"}
            ))
            customer.sedar_active_contract_count = len(customer.sedar_marketing_contract_ids.filtered(
                lambda item: item.status == "active"
            ))
            customer.sedar_completed_service_count = len(orders.filtered(
                lambda item: item.state in {"completed", "billing_ready", "closed"}
            ))

    @api.constrains("sedar_primary_contact_id")
    def _check_sedar_primary_contact(self):
        for customer in self:
            contact = customer.sedar_primary_contact_id
            if contact and contact.commercial_partner_id != customer.commercial_partner_id:
                raise ValidationError("The primary contact must belong to this customer account.")

    @api.constrains("sedar_preferred_contact_start", "sedar_preferred_contact_end")
    def _check_sedar_contact_window(self):
        for contact in self:
            if contact.sedar_preferred_contact_start and contact.sedar_preferred_contact_end:
                if contact.sedar_preferred_contact_end <= contact.sedar_preferred_contact_start:
                    raise ValidationError("Available Until must be later than Available From.")

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if partner.sedar_is_customer_account and not partner.sedar_customer_code:
                partner.sedar_customer_code = self.env["ir.sequence"].next_by_code("sedar.marketing.customer") or "New"
            customer = partner if partner.sedar_is_customer_account else partner.commercial_partner_id
            if customer.sedar_is_customer_account:
                module = "customer" if partner == customer else "contacts"
                self.env["sedar.marketing.activity"].log(
                    customer, module, "created",
                    f"{'Customer account' if partner == customer else 'Contact'} {partner.display_name} created.",
                    partner,
                )
        return partners

    def write(self, vals):
        tracked = {
            "name", "email", "phone", "mobile", "function", "sedar_account_status",
            "sedar_assigned_marketing_user_id", "sedar_relationship_status",
            "sedar_primary_contact_id", "sedar_contact_status", "sedar_contact_type_ids",
            "sedar_can_approve_quotations", "sedar_can_sign_contracts",
            "sedar_can_coordinate_operations",
        }
        snapshots = {record.id: {name: record[name] for name in tracked.intersection(vals)} for record in self}
        result = super().write(vals)
        if self.env.context.get("sedar_skip_marketing_log"):
            return result
        for partner in self:
            customer = partner if partner.sedar_is_customer_account else partner.commercial_partner_id
            if not customer.sedar_is_customer_account:
                continue
            changes = [
                (name, snapshots[partner.id].get(name), partner[name])
                for name in tracked.intersection(vals)
                if snapshots[partner.id].get(name) != partner[name]
            ]
            if changes:
                module = "customer" if partner == customer else "contacts"
                action = "status_changed" if any(name.endswith("status") for name, _, _ in changes) else "updated"
                self.env["sedar.marketing.activity"].log(
                    customer, module, action, f"{partner.display_name} updated.", partner, changes
                )
        return result


class SedarMarketingInternalNote(models.Model):
    _name = "sedar.marketing.internal.note"
    _description = "SEDAR Marketing Internal Note"
    _order = "create_date desc, id desc"

    customer_id = fields.Many2one("res.partner", required=True, index=True, ondelete="cascade")
    author_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    note = fields.Text(required=True)

    @api.model_create_multi
    def create(self, vals_list):
        notes = super().create(vals_list)
        for note in notes:
            self.env["sedar.marketing.activity"].log(
                note.customer_id, "customer", "note_added", "Internal Marketing note added.", note,
                changes=[("note", False, note.note)], visibility="restricted",
            )
        return notes

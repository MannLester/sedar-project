from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarMarketingContract(models.Model):
    _name = "sedar.marketing.contract"
    _description = "SEDAR Marketing Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Contract", default="New", readonly=True, copy=False, index=True)
    title = fields.Char(required=True, tracking=True)
    customer_id = fields.Many2one("res.partner", required=True, index=True, ondelete="restrict", tracking=True)
    contact_id = fields.Many2one("res.partner", required=True, ondelete="restrict", tracking=True)
    quotation_id = fields.Many2one(
        "sedar.marketing.quotation", required=True, index=True, ondelete="restrict", tracking=True
    )
    service_order_id = fields.Many2one(
        "sedar.marine.service.order", string="Service Request", required=True,
        index=True, ondelete="restrict", tracking=True
    )
    service_type_id = fields.Many2one("sedar.marine.service.type", readonly=True)
    vessel_name = fields.Char(readonly=True)
    description = fields.Text()
    effective_date = fields.Date(required=True, tracking=True)
    expiration_date = fields.Date(required=True, tracking=True)
    contract_value = fields.Monetary(required=True, tracking=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    terms_and_conditions = fields.Text()
    internal_notes = fields.Text()
    prepared_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    managed_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    status = fields.Selection([
        ("draft", "Draft"), ("internal_review", "For Internal Review"),
        ("ready_signature", "Ready for Signature"),
        ("awaiting_signatures", "Awaiting Signatures"), ("active", "Active"),
        ("terminated", "Terminated"), ("expired", "Expired"),
        ("superseded", "Superseded"),
    ], default="draft", required=True, tracking=True, index=True, copy=False)
    signature_status = fields.Selection([
        ("not_started", "Not Started"), ("sedar_signed", "SEDAR Signed"),
        ("customer_signed", "Customer Signed"), ("fully_executed", "Fully Executed"),
        ("declined", "Declined"),
    ], compute="_compute_signature_status", store=True, tracking=True)
    signature_ids = fields.One2many("sedar.marketing.contract.signature", "contract_id", copy=True)
    selected_customer_contact_id = fields.Many2one("res.partner", ondelete="restrict")
    sent_for_signature_at = fields.Datetime(readonly=True, copy=False)
    fully_executed_at = fields.Datetime(readonly=True, copy=False)
    submitted_for_internal_review_at = fields.Datetime(readonly=True, copy=False)
    termination_reason = fields.Selection([
        ("customer", "Customer Request"), ("breach", "Breach of Terms"),
        ("operational", "Operational Limitation"), ("mutual", "Mutual Agreement"),
        ("not_required", "Service No Longer Required"), ("other", "Other"),
    ], copy=False)
    termination_explanation = fields.Text(copy=False)
    requested_termination_date = fields.Date(copy=False)
    termination_request_status = fields.Selection([
        ("pending", "Pending Review"), ("approved", "Approved"), ("rejected", "Rejected")
    ], copy=False)
    termination_requested_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    termination_requested_at = fields.Datetime(readonly=True, copy=False)
    terminated_at = fields.Datetime(readonly=True, copy=False)
    termination_effective_date = fields.Date(readonly=True, copy=False)
    supersedes_contract_id = fields.Many2one("sedar.marketing.contract", readonly=True, copy=False, ondelete="restrict")
    superseded_by_contract_id = fields.Many2one("sedar.marketing.contract", readonly=True, copy=False, ondelete="restrict")

    _name_unique = models.Constraint("UNIQUE(name)", "Contract number must be unique.")

    @api.depends("signature_ids.party", "signature_ids.verification_status")
    def _compute_signature_status(self):
        for contract in self:
            verified = contract.signature_ids.filtered(lambda item: item.verification_status == "verified")
            sedar = bool(verified.filtered(lambda item: item.party == "sedar"))
            customer = bool(verified.filtered(lambda item: item.party == "customer"))
            declined = bool(contract.signature_ids.filtered(lambda item: item.verification_status == "rejected"))
            if declined:
                contract.signature_status = "declined"
            elif sedar and customer:
                contract.signature_status = "fully_executed"
            elif sedar:
                contract.signature_status = "sedar_signed"
            elif customer:
                contract.signature_status = "customer_signed"
            else:
                contract.signature_status = "not_started"

    @api.constrains("customer_id", "contact_id", "quotation_id", "service_order_id", "effective_date", "expiration_date", "contract_value")
    def _check_contract(self):
        for contract in self:
            customer = contract.customer_id.commercial_partner_id
            if contract.contact_id.commercial_partner_id != customer:
                raise ValidationError("The contract contact must belong to the customer.")
            if contract.quotation_id.customer_id.commercial_partner_id != customer:
                raise ValidationError("The contract quotation must belong to the customer.")
            if contract.service_order_id.client_id.commercial_partner_id != customer:
                raise ValidationError("The contract Service Request must belong to the customer.")
            if contract.expiration_date <= contract.effective_date:
                raise ValidationError("Contract expiration must be later than its effective date.")
            if contract.contract_value < 0:
                raise ValidationError("Contract value cannot be negative.")

    @api.onchange("quotation_id")
    def _onchange_quotation_id(self):
        if self.quotation_id:
            quotation = self.quotation_id
            self.customer_id = quotation.customer_id
            self.contact_id = quotation.contact_id
            self.service_order_id = quotation.service_order_id
            self.service_type_id = quotation.service_order_id.service_type_id
            self.vessel_name = quotation.service_order_id.assisted_vessel_name
            self.contract_value = quotation.amount_total
            self.currency_id = quotation.currency_id
            self.title = quotation.subject

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("sedar.marketing.contract") or "New"
        contracts = super().create(vals_list)
        for contract in contracts:
            self.env["sedar.marketing.activity"].log(
                contract.customer_id, "contracts", "created",
                f"Contract {contract.name} created.", contract,
            )
            self.env["sedar.marketing.transaction"].sync_contract(contract)
        return contracts

    def write(self, vals):
        before = {item.id: item.status for item in self}
        result = super().write(vals)
        if self.env.context.get("sedar_skip_contract_log"):
            return result
        for contract in self:
            if "status" in vals and before[contract.id] != contract.status:
                self.env["sedar.marketing.activity"].log(
                    contract.customer_id, "contracts", "status_changed",
                    f"Contract {contract.name} changed status.", contract,
                    [("status", before[contract.id], contract.status)],
                )
            elif vals:
                self.env["sedar.marketing.activity"].log(
                    contract.customer_id, "contracts", "updated",
                    f"Contract {contract.name} updated.", contract,
                )
            self.env["sedar.marketing.transaction"].sync_contract(contract)
        return result

    def action_submit_internal_review(self):
        self._require_status("draft")
        if any(item.quotation_id.status != "customer_approved" for item in self):
            raise UserError("Only a customer-approved quotation may proceed to contract review.")
        self.write({"status": "internal_review", "submitted_for_internal_review_at": fields.Datetime.now()})

    def action_approve_internal_review(self):
        self._require_status("internal_review")
        self.write({"status": "ready_signature"})

    def action_send_for_signature(self):
        self._require_status("ready_signature")
        if any(not item.selected_customer_contact_id for item in self):
            raise UserError("Select an authorized customer signatory before sending the contract.")
        if any(not item.selected_customer_contact_id.sedar_can_sign_contracts for item in self):
            raise UserError("The selected customer contact is not authorized to sign contracts.")
        self.write({"status": "awaiting_signatures", "sent_for_signature_at": fields.Datetime.now()})

    def action_activate(self):
        self._require_status("awaiting_signatures")
        if any(item.signature_status != "fully_executed" for item in self):
            raise UserError("Both SEDAR and customer signatures must be verified before activation.")
        self.write({"status": "active", "fully_executed_at": fields.Datetime.now()})

    def action_request_termination(self):
        self._require_status("active")
        if any(not item.termination_reason or not item.requested_termination_date for item in self):
            raise UserError("A termination reason and requested date are required.")
        self.write({
            "termination_request_status": "pending",
            "termination_requested_by_id": self.env.user.id,
            "termination_requested_at": fields.Datetime.now(),
        })

    def action_approve_termination(self):
        if any(item.termination_request_status != "pending" for item in self):
            raise UserError("Only a pending termination request may be approved.")
        self.write({
            "termination_request_status": "approved", "status": "terminated",
            "terminated_at": fields.Datetime.now(),
            "termination_effective_date": fields.Date.context_today(self),
        })

    def _require_status(self, *allowed):
        if any(item.status not in allowed for item in self):
            raise UserError(f"This action requires contract status: {', '.join(allowed)}.")


class SedarMarketingContractSignature(models.Model):
    _name = "sedar.marketing.contract.signature"
    _description = "SEDAR Marketing Contract Signature Record"
    _order = "signed_at, id"

    contract_id = fields.Many2one("sedar.marketing.contract", required=True, ondelete="cascade", index=True)
    party = fields.Selection([("sedar", "SEDAR"), ("customer", "Customer")], required=True)
    signatory_name = fields.Char(required=True)
    organization = fields.Char(required=True)
    position = fields.Char()
    signature_role = fields.Char()
    signed_at = fields.Datetime(required=True, default=fields.Datetime.now)
    recorded_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    supporting_document_name = fields.Char(help="Metadata only; signature file bytes stay with the owning document system.")
    verification_status = fields.Selection([
        ("pending", "Pending Verification"), ("verified", "Verified"), ("rejected", "Rejected")
    ], default="pending", required=True)
    internal_notes = fields.Text()

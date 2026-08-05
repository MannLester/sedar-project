from odoo import api, fields, models
from odoo.exceptions import AccessError


class SedarMarketingTransaction(models.Model):
    _name = "sedar.marketing.transaction"
    _description = "SEDAR Customer Transaction Projection"
    _order = "occurred_at desc, id desc"

    customer_id = fields.Many2one("res.partner", required=True, index=True, ondelete="cascade")
    occurred_at = fields.Datetime(required=True, index=True)
    transaction_type = fields.Selection([
        ("service_request", "Service Request"), ("quotation", "Quotation"),
        ("contract_request", "Contract Request"), ("contract", "Contract"),
        ("completed_service", "Completed Service"), ("invoice", "Invoice"),
        ("payment", "Payment"), ("credit_note", "Credit Note"),
    ], required=True, index=True)
    reference = fields.Char(required=True, index=True)
    description = fields.Char(required=True)
    amount = fields.Monetary()
    currency_id = fields.Many2one("res.currency", required=True)
    status = fields.Char(required=True, index=True)
    source_department = fields.Selection([
        ("marketing", "Marketing"), ("operations", "Operations"),
        ("document_control", "Document Control"), ("finance", "Finance"),
    ], required=True)
    visibility = fields.Selection([
        ("customer", "Customer Visible"), ("internal", "Internal")
    ], default="internal", required=True)
    source_model = fields.Char(required=True, index=True)
    source_record_id = fields.Integer(required=True, index=True)
    vessel_name = fields.Char()
    service_type = fields.Char()
    purchase_order_reference = fields.Char()

    _source_unique = models.Constraint(
        "UNIQUE(source_model, source_record_id, transaction_type)",
        "A source record may only have one projection for each transaction type.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sedar_transaction_sync"):
            raise AccessError("Transaction History is read-only and system-maintained.")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("sedar_transaction_sync"):
            raise AccessError("Transaction History is read-only and system-maintained.")
        return super().write(vals)

    def unlink(self):
        raise AccessError("Transaction History records cannot be deleted.")

    @api.model
    def _upsert(self, source, transaction_type, values):
        record = self.sudo().search([
            ("source_model", "=", source._name),
            ("source_record_id", "=", source.id),
            ("transaction_type", "=", transaction_type),
        ], limit=1)
        values = dict(
            values,
            transaction_type=transaction_type,
            source_model=source._name,
            source_record_id=source.id,
        )
        target = self.sudo().with_context(sedar_transaction_sync=True)
        if record:
            record.with_context(sedar_transaction_sync=True).write(values)
            return record
        return target.create(values)

    @api.model
    def sync_service_order(self, order):
        transaction_type = "completed_service" if order.state in {"completed", "billing_ready", "closed"} else "service_request"
        status = dict(order._fields["marketing_status"].selection).get(order.marketing_status, order.marketing_status)
        return self._upsert(order, transaction_type, {
            "customer_id": order.client_id.commercial_partner_id.id,
            "occurred_at": order.write_date or order.create_date or fields.Datetime.now(),
            "reference": order.name,
            "description": f"{order.service_type_id.name} · {order.assisted_vessel_name}",
            "amount": order.estimated_amount,
            "currency_id": order.currency_id.id,
            "status": status,
            "source_department": "operations" if transaction_type == "completed_service" else "marketing",
            "visibility": "customer",
            "vessel_name": order.assisted_vessel_name,
            "service_type": order.service_type_id.name,
            "purchase_order_reference": order.client_reference,
        })

    @api.model
    def sync_quotation(self, quotation):
        status = dict(quotation._fields["status"].selection).get(quotation.status, quotation.status)
        return self._upsert(quotation, "quotation", {
            "customer_id": quotation.customer_id.commercial_partner_id.id,
            "occurred_at": quotation.write_date or quotation.create_date or fields.Datetime.now(),
            "reference": quotation.name,
            "description": quotation.subject,
            "amount": quotation.amount_total,
            "currency_id": quotation.currency_id.id,
            "status": status,
            "source_department": "marketing", "visibility": "customer",
            "vessel_name": quotation.service_order_id.assisted_vessel_name,
            "service_type": quotation.service_order_id.service_type_id.name,
            "purchase_order_reference": quotation.purchase_order_reference,
        })

    @api.model
    def sync_contract(self, contract):
        status = dict(contract._fields["status"].selection).get(contract.status, contract.status)
        return self._upsert(contract, "contract", {
            "customer_id": contract.customer_id.commercial_partner_id.id,
            "occurred_at": contract.write_date or contract.create_date or fields.Datetime.now(),
            "reference": contract.name,
            "description": contract.title,
            "amount": contract.contract_value,
            "currency_id": contract.currency_id.id,
            "status": status,
            "source_department": "marketing", "visibility": "customer",
            "vessel_name": contract.vessel_name,
            "service_type": contract.service_type_id.name,
        })

    @api.model
    def sync_invoice(self, invoice):
        order = invoice.sedar_service_order_id
        if not order or not order.client_id.sedar_is_customer_account:
            return self.browse()
        transaction_type = "credit_note" if invoice.move_type == "out_refund" else "invoice"
        status = dict(invoice._fields["payment_state"].selection).get(invoice.payment_state, invoice.state)
        projected = self._upsert(invoice, transaction_type, {
            "customer_id": order.client_id.commercial_partner_id.id,
            "occurred_at": invoice.write_date or invoice.create_date or fields.Datetime.now(),
            "reference": invoice.name or invoice.ref or "Draft Invoice",
            "description": f"Invoice for {order.name}",
            "amount": -invoice.amount_total if transaction_type == "credit_note" else invoice.amount_total,
            "currency_id": invoice.currency_id.id,
            "status": status,
            "source_department": "finance", "visibility": "customer",
            "vessel_name": order.assisted_vessel_name,
            "service_type": order.service_type_id.name,
        })
        paid_amount = invoice.amount_total - invoice.amount_residual
        if transaction_type == "invoice" and paid_amount > 0:
            self._upsert(invoice, "payment", {
                "customer_id": order.client_id.commercial_partner_id.id,
                "occurred_at": invoice.write_date or fields.Datetime.now(),
                "reference": f"PAY-{invoice.name or invoice.id}",
                "description": f"Payment recorded against {invoice.name or 'invoice'}",
                "amount": paid_amount, "currency_id": invoice.currency_id.id,
                "status": "Paid" if invoice.payment_state == "paid" else "Partially Paid",
                "source_department": "finance", "visibility": "customer",
            })
        return projected


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            self.env["sedar.marketing.transaction"].sync_invoice(move)
        return moves

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("sedar_skip_marketing_transaction"):
            for move in self:
                self.env["sedar.marketing.transaction"].sync_invoice(move)
        return result

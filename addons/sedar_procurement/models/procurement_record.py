from odoo import fields, models


class SedarProcurementRecord(models.Model):
    _name = "sedar.procurement.record"
    _description = "SEDAR Procurement Record"
    _order = "request_date desc, name"

    name = fields.Char(required=True)
    flow_step = fields.Selection(
        [
            ("request_info", "Request Info"),
            ("items", "Items"),
            ("supplier_budget", "Supplier / Budget"),
            ("supplier_info", "Supplier Info"),
            ("rfq_details", "RFQ Details"),
            ("terms", "Terms"),
            ("po_details", "PO Details"),
            ("review", "Review"),
        ],
        default="request_info",
        required=True,
    )
    record_type = fields.Selection(
        [("pr", "Purchase Request"), ("rfq", "RFQ"), ("po", "Purchase Order")], default="pr"
    )
    priority = fields.Selection(
        [("normal", "Normal"), ("urgent", "Urgent"), ("critical", "Critical")],
        default="normal",
    )
    item_name = fields.Char()
    item_description = fields.Text()
    quantity = fields.Float(default=1)
    unit_of_measure = fields.Char(default="pcs")
    needed_by = fields.Date()
    purpose = fields.Char()
    budget_source = fields.Char()
    payment_terms = fields.Char(default="30 days")
    supplier_contact = fields.Char()
    supplier_email = fields.Char()
    supplier_phone = fields.Char()
    rfq_scope = fields.Text()
    quote_deadline = fields.Date()
    delivery_location = fields.Char()
    warranty_terms = fields.Char()
    supplier = fields.Char()
    requested_by = fields.Char()
    request_date = fields.Date()
    amount = fields.Float()
    expected_delivery = fields.Date()
    approval_age_days = fields.Integer()
    supplier_lead_days = fields.Integer()
    delivery_performance = fields.Selection(
        [("good", "On Track"), ("watch", "Watch"), ("risk", "Risk")],
        default="good",
    )
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("ordered", "Ordered"),
            ("received", "Received"),
        ],
        default="draft",
    )
    approval_owner = fields.Char()
    maintenance_id = fields.Many2one("sedar.maintenance.work.order")
    inventory_id = fields.Many2one("sedar.inventory.item")
    note = fields.Text()

    def action_save_draft(self):
        self.write({"status": "draft"})
        return self.env.ref("sedar_procurement.action_sedar_procurement_records_board").read()[0]

    def action_next_step(self):
        next_steps = {
            "request_info": "items",
            "items": "supplier_budget",
            "supplier_budget": "review",
            "supplier_info": "rfq_details",
            "rfq_details": "terms",
            "terms": "review",
            "po_details": "review",
            "review": "review",
        }
        for record in self:
            values = {"flow_step": next_steps.get(record.flow_step, "items")}
            if record.flow_step in ["request_info", "items", "supplier_budget"]:
                values["record_type"] = "pr"
            elif record.flow_step in ["supplier_info", "rfq_details", "terms"]:
                values["record_type"] = "rfq"
            elif record.flow_step == "po_details":
                values["record_type"] = "po"
            record.write(values)
        return True

    def action_previous_step(self):
        previous_steps = {
            "items": "request_info",
            "supplier_budget": "items",
            "rfq_details": "supplier_info",
            "terms": "rfq_details",
            "po_details": "po_details",
            "review": "supplier_budget",
            "request_info": "request_info",
            "supplier_info": "supplier_info",
        }
        for record in self:
            if record.record_type == "po" and record.flow_step == "review":
                record.write({"flow_step": "po_details"})
            elif record.record_type == "rfq" and record.flow_step == "review":
                record.write({"flow_step": "terms"})
            else:
                record.write({"flow_step": previous_steps.get(record.flow_step, "request_info")})
        return True

    def action_submit_request(self):
        for record in self:
            values = {"flow_step": "review", "status": "pending_approval"}
            if record.record_type == "po":
                values["status"] = "ordered"
            elif record.record_type != "rfq":
                values["record_type"] = "pr"
            record.write(values)
        return self.env.ref("sedar_procurement.action_sedar_procurement_dashboard").read()[0]

    def action_create_po_from_record(self):
        self.ensure_one()
        source = self
        details = source.item_description or source.rfq_scope or source.note
        return {
            "type": "ir.actions.act_window",
            "name": "Create Purchase Order",
            "res_model": "sedar.procurement.record",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_name": source.name.replace("RFQ", "PO", 1).replace("PR", "PO", 1) if source.name else "New Purchase Order",
                "default_record_type": "po",
                "default_flow_step": "po_details",
                "default_status": "draft",
                "default_supplier": source.supplier,
                "default_requested_by": source.requested_by,
                "default_item_name": source.item_name,
                "default_item_description": details,
                "default_quantity": source.quantity,
                "default_unit_of_measure": source.unit_of_measure,
                "default_amount": source.amount,
                "default_expected_delivery": source.expected_delivery or source.needed_by,
                "default_payment_terms": source.payment_terms,
                "default_supplier_lead_days": source.supplier_lead_days,
                "default_delivery_performance": source.delivery_performance,
                "default_approval_owner": source.approval_owner,
                "default_maintenance_id": source.maintenance_id.id,
                "default_inventory_id": source.inventory_id.id,
            },
        }

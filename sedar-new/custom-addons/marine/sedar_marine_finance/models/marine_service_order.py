import math
from odoo import Command, api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarMarineServiceOrder(models.Model):
    _inherit = "sedar.marine.service.order"

    terminal_id = fields.Many2one(
        "sedar.marine.berth", string="Service Terminal", tracking=True,
        domain="[('port_id', '=', port_id)]",
    )
    confirmed_tariff_id = fields.Many2one("sedar.client.tariff", readonly=True, copy=False)
    confirmed_pricing_basis = fields.Selection([
        ("per_service", "Per Service"), ("per_tug", "Per Tug"),
        ("per_hour", "Per Hour"), ("per_tug_hour", "Per Tug-Hour"),
        ("per_day", "Per Day"), ("quotation", "Quotation Required"),
    ], string="Confirmed Pricing Basis", readonly=True, copy=False)
    confirmed_unit_rate = fields.Monetary(readonly=True, copy=False, currency_field="confirmed_currency_id")
    confirmed_minimum_charge = fields.Monetary(readonly=True, copy=False, currency_field="confirmed_currency_id")
    confirmed_currency_id = fields.Many2one("res.currency", readonly=True, copy=False)
    pricing_frozen_at = fields.Datetime(readonly=True, copy=False)
    confirmed_service_date = fields.Date(readonly=True, copy=False)
    confirmed_service_date_changed = fields.Boolean(compute="_compute_confirmed_service_date_changed", store=True)
    billing_reviewed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    billing_reviewed_at = fields.Datetime(readonly=True, copy=False)
    automated_completion_handoff = fields.Boolean(
        compute="_compute_automated_completion_handoff", store=True,
        help="True only after the Marine Operation and Service Order are completed and every active tug completion is submitted.",
    )
    billing_note = fields.Text()
    billing_adjustment_ids = fields.One2many("sedar.marine.billing.adjustment", "order_id", string="Billing Adjustments")
    actual_billable_quantity = fields.Float(compute="_compute_final_billing", store=True)
    base_billable_amount = fields.Monetary(compute="_compute_final_billing", store=True, currency_field="confirmed_currency_id")
    adjustment_amount = fields.Monetary(compute="_compute_final_billing", store=True, currency_field="confirmed_currency_id")
    total_billable_amount = fields.Monetary(compute="_compute_final_billing", store=True, currency_field="confirmed_currency_id")
    invoice_ids = fields.One2many("account.move", "sedar_service_order_id", string="Invoices")
    invoice_count = fields.Integer(compute="_compute_billing_status", store=True)
    billing_status = fields.Selection([
        ("not_ready", "Not Ready"), ("review", "Billing Review"),
        ("pricing_exception", "Pricing Exception"), ("draft_invoice", "Draft Invoice"),
        ("invoiced", "Invoiced"), ("partial", "Partial / In Payment"),
        ("paid", "Paid"), ("cancelled", "Cancelled / Credited"),
    ], compute="_compute_billing_status", store=True)

    def action_confirm(self):
        result = super().action_confirm()
        self._freeze_pricing()
        return result

    def _freeze_pricing(self):
        for order in self:
            tariff = order.tariff_id
            valid = bool(
                tariff and tariff.approved and order.terminal_id
                and tariff.port_id == order.port_id and tariff.terminal_id == order.terminal_id
                and getattr(tariff, "approval_state", "approved") == "approved"
            )
            order.with_context(sedar_finance_internal=True).write({
                "confirmed_tariff_id": tariff.id if valid else False,
                "confirmed_pricing_basis": order.pricing_basis if valid else False,
                "confirmed_unit_rate": order.unit_rate if valid else 0,
                "confirmed_minimum_charge": order.minimum_charge if valid else 0,
                "confirmed_currency_id": order.currency_id.id,
                "confirmed_service_date": fields.Date.to_date(order.requested_start),
                "pricing_frozen_at": fields.Datetime.now(),
            })

    def _find_tariff(self):
        self.ensure_one()
        if not self.client_id or not self.service_type_id or not self.terminal_id:
            return self.env["sedar.client.tariff"]
        tariff_date = fields.Date.to_date(self.requested_start) or fields.Date.context_today(self)
        domain = [
            ("partner_id", "=", self.client_id.commercial_partner_id.id),
            ("service_type_id", "=", self.service_type_id.id),
            ("terminal_id", "=", self.terminal_id.id),
            ("approved", "=", True),
            ("approval_state", "=", "approved"),
            ("active", "=", True),
            ("valid_from", "<=", tariff_date),
            "|", ("valid_until", "=", False), ("valid_until", ">=", tariff_date),
        ]
        tariffs = self.env["sedar.client.tariff"].search(domain, order="valid_from desc, id desc")
        exact = tariffs.filtered(
            lambda tariff: tariff.port_id == self.port_id
            and (not tariff.tug_class_id or tariff.tug_class_id == self.tug_class_id)
        )
        return exact[:1]

    @api.onchange("terminal_id")
    def _onchange_terminal_tariff(self):
        self._apply_tariff()

    @api.model_create_multi
    def create(self, vals_list):
        if (
            not self.env.su
            and not self.env.user.has_group("base.group_system")
            and self.env.user.has_group("sedar_marine_finance.group_billing_officer")
        ):
            raise AccessError(_("Billing Officers review existing Service Orders and cannot create them."))
        return super().create(vals_list)

    def write(self, vals):
        frozen_fields = {
            "confirmed_tariff_id", "confirmed_pricing_basis", "confirmed_unit_rate",
            "confirmed_minimum_charge", "confirmed_currency_id", "pricing_frozen_at",
            "confirmed_service_date", "billing_reviewed_by_id", "billing_reviewed_at",
        }
        if frozen_fields.intersection(vals) and not self.env.context.get("sedar_finance_internal") and not self.env.su:
            raise AccessError(_("Frozen pricing and billing audit fields can only be changed by workflow actions."))
        if "billing_note" in vals and not self.env.user.has_group("sedar_marine_finance.group_billing_officer") and not self.env.su:
            raise AccessError(_("Only Finance may update the billing note."))
        if (
            not self.env.su
            and not self.env.user.has_group("base.group_system")
            and self.env.user.has_group("sedar_marine_finance.group_billing_officer")
            and not any(self.env.context.get(key) for key in (
                "sedar_finance_internal", "sedar_operation_sync", "sedar_readiness_sync",
            ))
            and set(vals) - {"billing_note"}
        ):
            raise AccessError(_("Billing Officers may review Service Orders and update only the billing note."))
        return super().write(vals)

    @api.depends("requested_start", "confirmed_service_date")
    def _compute_confirmed_service_date_changed(self):
        for order in self:
            order.confirmed_service_date_changed = bool(
                order.confirmed_service_date
                and fields.Date.to_date(order.requested_start) != order.confirmed_service_date
            )

    @api.depends(
        "confirmed_pricing_basis", "confirmed_unit_rate", "confirmed_minimum_charge",
        "tug_assignment_ids.state", "tug_assignment_ids.completion_state",
        "tug_assignment_ids.actual_start", "tug_assignment_ids.actual_end",
        "billing_adjustment_ids.amount",
    )
    def _compute_final_billing(self):
        for order in self:
            assignments = order.tug_assignment_ids.filtered(
                lambda a: a.state != "cancelled" and a.completion_state == "submitted"
                and a.actual_start and a.actual_end
            )
            hours = [max(0.0, (a.actual_end - a.actual_start).total_seconds() / 3600.0) for a in assignments]
            basis = order.confirmed_pricing_basis
            if basis == "per_service":
                quantity = 1.0
            elif basis == "per_tug":
                quantity = float(len(assignments))
            elif basis == "per_tug_hour":
                quantity = sum(hours)
            elif basis == "per_hour":
                quantity = ((max(assignments.mapped("actual_end")) - min(assignments.mapped("actual_start"))).total_seconds() / 3600.0) if assignments else 0.0
            elif basis == "per_day":
                quantity = float(math.ceil(sum(hours) / 24.0)) if hours else 0.0
            else:
                quantity = 0.0
            calculated = order.confirmed_unit_rate * quantity
            order.actual_billable_quantity = quantity
            order.base_billable_amount = max(calculated, order.confirmed_minimum_charge) if quantity else 0.0
            order.adjustment_amount = sum(order.billing_adjustment_ids.mapped("amount"))
            order.total_billable_amount = order.base_billable_amount + order.adjustment_amount

    @api.depends(
        "state", "operation_ids.state", "tug_assignment_ids.state",
        "tug_assignment_ids.completion_state", "number_of_tugs",
    )
    def _compute_automated_completion_handoff(self):
        for order in self:
            active_tugs = order.tug_assignment_ids.filtered(lambda tug: tug.state != "cancelled")
            active_operations = order.operation_ids.filtered(lambda operation: operation.state != "cancelled")
            order.automated_completion_handoff = bool(
                order.state == "completed"
                and len(active_operations) == 1
                and active_operations.state == "completed"
                and len(active_tugs) >= order.number_of_tugs
                and all(tug.completion_state == "submitted" for tug in active_tugs)
            )

    @api.depends(
        "state", "automated_completion_handoff", "confirmed_tariff_id",
        "confirmed_service_date_changed", "terminal_id",
        "invoice_ids.state", "invoice_ids.payment_state",
    )
    def _compute_billing_status(self):
        for order in self:
            invoices = order.invoice_ids.filtered(lambda m: m.move_type == "out_invoice")
            active = invoices.filtered(lambda m: m.state != "cancel")
            order.invoice_count = len(invoices)
            if active and all(m.payment_state == "reversed" for m in active):
                status = "cancelled"
            elif active and all(m.payment_state == "paid" for m in active):
                status = "paid"
            elif any(m.payment_state in {"partial", "in_payment"} for m in active):
                status = "partial"
            elif any(m.state == "posted" for m in active):
                status = "invoiced"
            elif active:
                status = "draft_invoice"
            elif not order.automated_completion_handoff:
                status = "not_ready"
            elif not order.confirmed_tariff_id or not order.terminal_id or order.confirmed_service_date_changed:
                status = "pricing_exception"
            else:
                status = "review"
            order.billing_status = status

    def action_mark_billing_reviewed(self):
        if not self.env.user.has_group("sedar_marine_finance.group_billing_officer"):
            raise AccessError(_("Only a Billing Officer may complete billing review."))
        for order in self:
            if order.billing_status != "review":
                raise UserError(_("This order is not ready for billing review."))
            if not order.automated_completion_handoff:
                raise UserError(_("Billing requires the automated completed-operation handoff."))
            active = order.tug_assignment_ids.filtered(lambda a: a.state != "cancelled")
            if not active or any(a.completion_state != "submitted" for a in active):
                raise UserError(_("Every active tug must have a submitted Tug Master completion."))
            if order.total_billable_amount < 0:
                raise ValidationError(_("The final invoice total cannot be negative."))
            order.with_context(sedar_finance_internal=True).write({
                "billing_reviewed_by_id": self.env.user.id,
                "billing_reviewed_at": fields.Datetime.now(),
            })
        return True

    def action_create_draft_invoice(self):
        self.ensure_one()
        if not self.env.user.has_group("sedar_marine_finance.group_billing_officer"):
            raise AccessError(_("Only a Billing Officer may create the customer invoice."))
        if self.billing_status != "review" or not self.billing_reviewed_at:
            raise UserError(_("Complete Billing Review before creating an invoice."))
        if self.invoice_ids.filtered(lambda m: m.move_type == "out_invoice" and m.state != "cancel"):
            raise UserError(_("An active customer invoice already exists for this Service Order."))
        product = self.env.ref("sedar_marine_finance.product_marine_service")
        lines = [Command.create({
            "product_id": product.id,
            "name": _("Marine service %s (%s × %s)") % (self.name, self.actual_billable_quantity, self.confirmed_pricing_basis),
            "quantity": 1.0,
            "price_unit": self.base_billable_amount,
        })]
        for adjustment in self.billing_adjustment_ids:
            lines.append(Command.create({
                "product_id": product.id,
                "name": "%s — %s" % (adjustment.description, adjustment.reason),
                "quantity": adjustment.quantity,
                "price_unit": adjustment.unit_rate * (-1 if adjustment.adjustment_type == "deduction" else 1),
            }))
        invoice = self.env["account.move"].with_company(self.company_id).create({
            "move_type": "out_invoice",
            "company_id": self.company_id.id,
            "partner_id": self.client_id.commercial_partner_id.id,
            "currency_id": self.confirmed_currency_id.id,
            "invoice_origin": self.name,
            "ref": self.client_reference or self.name,
            "sedar_service_order_id": self.id,
            "invoice_line_ids": lines,
        })
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": invoice.id, "view_mode": "form"}

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Customer Invoices"),
            "res_model": "account.move", "view_mode": "list,form",
            "domain": [("sedar_service_order_id", "=", self.id)],
            "context": {"default_move_type": "out_invoice", "default_sedar_service_order_id": self.id},
        }


class SedarTugAssignment(models.Model):
    _inherit = "sedar.tug.assignment"

    def action_return_completion(self):
        if not self.env.user.has_group("sedar_marine_finance.group_billing_officer"):
            return super().action_return_completion()
        for assignment in self:
            if assignment.completion_state != "submitted":
                raise UserError(_("Only a submitted completion can be returned."))
            if not (assignment.completion_return_reason or "").strip():
                raise UserError(_("Enter a correction reason before returning the completion."))
            if assignment.order_id.invoice_ids.filtered(lambda m: m.state != "cancel"):
                raise UserError(_("Cancel the draft invoice before returning completion. Posted invoices require a credit note."))
            assignment.with_context(sedar_completion_action=True).write({
                "completion_state": "returned",
                "completion_declared_by_id": False,
                "completion_declared_at": False,
            })
        orders = self.mapped("order_id")
        orders.sync_completion_from_tugs()
        for order in orders:
            completed_operations = order.operation_ids.filtered(lambda operation: operation.state == "completed")
            if completed_operations:
                completed_operations.write({"state": "in_progress", "actual_end": False})
            order.with_context(sedar_finance_internal=True).write({
                "state": "in_progress",
                "billing_reviewed_by_id": False,
                "billing_reviewed_at": False,
            })
        return True

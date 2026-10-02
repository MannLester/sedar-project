from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarClientTariff(models.Model):
    _inherit = "sedar.client.tariff"

    terminal_id = fields.Many2one(
        "sedar.marine.berth", string="Terminal", ondelete="restrict",
        domain="[('port_id', '=', port_id)]",
    )
    approval_state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved"), ("superseded", "Superseded")],
        default="draft", required=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    approval_reference = fields.Char(
        string="President Authorization Reference", copy=False,
        help="Approval note or reference to the President's authorization.",
    )
    approval_attachment = fields.Binary(attachment=True, copy=False)
    approval_attachment_filename = fields.Char(copy=False)
    previous_version_id = fields.Many2one(
        "sedar.client.tariff", string="Previous Version", readonly=True, copy=False,
    )
    revision_ids = fields.One2many("sedar.client.tariff", "previous_version_id", string="Revisions")

    @api.depends("partner_id", "service_type_id", "port_id", "terminal_id")
    def _compute_name(self):
        for tariff in self:
            parts = [tariff.partner_id.name, tariff.service_type_id.name]
            if tariff.port_id:
                parts.append(tariff.port_id.name)
            if tariff.terminal_id:
                parts.append(tariff.terminal_id.name)
            tariff.name = " - ".join(filter(None, parts))

    def _check_tariff_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_marine_finance.group_accounting_manager"):
            raise AccessError(_("Only an Accounting Manager may govern client tariffs."))

    def action_approve(self):
        self._check_tariff_manager()
        for tariff in self:
            if not tariff.port_id or not tariff.terminal_id:
                raise ValidationError(_("A port and terminal are required before tariff approval."))
            if not tariff.approval_reference and not tariff.approval_attachment:
                raise ValidationError(_("Record the business authorization reference or attach its evidence."))
            overlap = self.search([
                ("id", "!=", tariff.id), ("approved", "=", True), ("active", "=", True),
                ("partner_id", "=", tariff.partner_id.id),
                ("service_type_id", "=", tariff.service_type_id.id),
                ("port_id", "=", tariff.port_id.id),
                ("terminal_id", "=", tariff.terminal_id.id),
                ("tug_class_id", "=", tariff.tug_class_id.id),
                ("valid_from", "<=", tariff.valid_until or fields.Date.to_date("9999-12-31")),
                "|", ("valid_until", "=", False), ("valid_until", ">=", tariff.valid_from),
            ], limit=1)
            if overlap and overlap != tariff.previous_version_id:
                raise ValidationError(_("This approval would overlap another approved tariff for the same client, terminal, service, and tug class."))
            if tariff.previous_version_id:
                if tariff.valid_from <= tariff.previous_version_id.valid_from:
                    raise ValidationError(_("A revision must start after its previous version."))
                tariff.previous_version_id.with_context(sedar_tariff_supersede=True).write({
                    "valid_until": fields.Date.subtract(tariff.valid_from, days=1),
                    "approval_state": "superseded",
                })
            tariff.write({
                "approved": True,
                "approval_state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
        return True

    def action_new_revision(self):
        self.ensure_one()
        self._check_tariff_manager()
        if self.approval_state != "approved":
            raise UserError(_("Only an approved tariff can be revised."))
        revision = self.copy({
            "approved": False,
            "approval_state": "draft",
            "approved_by_id": False,
            "approved_at": False,
            "approval_reference": False,
            "approval_attachment": False,
            "approval_attachment_filename": False,
            "previous_version_id": self.id,
            "valid_from": fields.Date.context_today(self),
            "valid_until": False,
        })
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": revision.id, "view_mode": "form"}

    def write(self, vals):
        governed = {
            "partner_id", "service_type_id", "port_id", "terminal_id", "tug_class_id", "pricing_basis",
            "rate", "minimum_charge", "currency_id", "valid_from", "valid_until",
            "approved", "approval_state", "approval_reference", "approval_attachment",
        }
        if governed.intersection(vals):
            self._check_tariff_manager()
        immutable = governed - {"approval_state"}
        if (not self.env.context.get("sedar_tariff_supersede") and immutable.intersection(vals)
                and any(t.approval_state == "approved" for t in self)):
            raise UserError(_("Approved tariffs are immutable. Create an effective-dated revision instead."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_tariff_manager()
        return super().create(vals_list)

    def unlink(self):
        self._check_tariff_manager()
        if any(tariff.approval_state in {"approved", "superseded"} for tariff in self):
            raise UserError(_("Approved tariff history cannot be deleted."))
        return super().unlink()


class SedarMarineBillingAdjustment(models.Model):
    _name = "sedar.marine.billing.adjustment"
    _description = "Marine Service Billing Adjustment"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one(
        "sedar.marine.service.order",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id", store=True, index=True, readonly=True
    )
    description = fields.Char(required=True)
    adjustment_type = fields.Selection([("charge", "Charge"), ("deduction", "Deduction")], required=True, default="charge")
    quantity = fields.Float(required=True, default=1.0)
    unit_rate = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="order_id.confirmed_currency_id", store=True)
    amount = fields.Monetary(compute="_compute_amount", store=True)
    reason = fields.Text(required=True)

    @api.depends("adjustment_type", "quantity", "unit_rate")
    def _compute_amount(self):
        for line in self:
            amount = line.quantity * line.unit_rate
            line.amount = -amount if line.adjustment_type == "deduction" else amount

    @api.constrains("quantity", "unit_rate", "description", "reason")
    def _check_values(self):
        for line in self:
            if line.quantity <= 0 or line.unit_rate < 0:
                raise ValidationError(_("Adjustment quantity must be positive and unit rate cannot be negative."))
            if not (line.description or "").strip() or not (line.reason or "").strip():
                raise ValidationError(_("Every billing adjustment requires a description and reason."))

    def _check_editable(self):
        if not self.env.user.has_group("sedar_marine_finance.group_billing_officer"):
            raise AccessError(_("Only Finance may maintain billing adjustments."))
        if any(line.order_id.invoice_ids.filtered(lambda m: m.state != "cancel") for line in self):
            raise UserError(_("Cancel the draft invoice before changing billing adjustments."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_editable()
        return records

    def write(self, vals):
        self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()

from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError


PRICING_BASES = [
    ("per_service", "Per Service"),
    ("per_tug", "Per Tug"),
    ("per_hour", "Per Hour"),
    ("per_tug_hour", "Per Tug-Hour"),
    ("per_day", "Per Day"),
    ("quotation", "Manual Quotation"),
]


class SedarMarineServiceType(models.Model):
    _name = "sedar.marine.service.type"
    _description = "Marine Service Type"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    pricing_basis = fields.Selection(PRICING_BASES, required=True, default="per_service")
    standard_rate = fields.Monetary()
    currency_id = fields.Many2one(
        "res.currency", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    requires_destination = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Service type code must be unique.")


class SedarMarinePort(models.Model):
    _name = "sedar.marine.port"
    _description = "Marine Port or Operating Area"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    timezone = fields.Selection(_tz_get, default="Asia/Manila")
    berth_ids = fields.One2many("sedar.marine.berth", "port_id")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Port code must be unique.")

class SedarMarineBerth(models.Model):
    _name = "sedar.marine.berth"
    _description = "Marine Berth or Service Location"
    _order = "port_id, name"

    name = fields.Char(required=True)
    code = fields.Char()
    port_id = fields.Many2one("sedar.marine.port", required=True, ondelete="cascade")
    active = fields.Boolean(default=True)


class SedarTugClass(models.Model):
    _name = "sedar.tug.class"
    _description = "Requested Tug Class"
    _order = "name"

    name = fields.Char(required=True)
    minimum_bollard_pull = fields.Float(string="Minimum Bollard Pull (T)")
    active = fields.Boolean(default=True)


class SedarClientVessel(models.Model):
    _name = "sedar.client.vessel"
    _description = "Client Vessel"
    _order = "name"

    name = fields.Char(required=True)
    owner_id = fields.Many2one("res.partner", string="Client", required=True, ondelete="restrict")
    imo_number = fields.Char(string="IMO Number", index=True)
    call_sign = fields.Char()
    vessel_type = fields.Selection([
        ("cargo", "Cargo Vessel"), ("tanker", "Tanker"),
        ("passenger", "Passenger Vessel"), ("barge", "Barge"),
        ("offshore", "Offshore Vessel"), ("other", "Other"),
    ], default="other")
    gross_tonnage = fields.Float()
    length_overall = fields.Float(string="Length Overall (m)")
    draft = fields.Float(string="Draft (m)")
    active = fields.Boolean(default=True)


class SedarClientTariff(models.Model):
    _name = "sedar.client.tariff"
    _description = "Client Marine Service Tariff"
    _order = "partner_id, service_type_id, valid_from desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    partner_id = fields.Many2one("res.partner", string="Client", required=True, ondelete="cascade")
    service_type_id = fields.Many2one("sedar.marine.service.type", required=True, ondelete="cascade")
    port_id = fields.Many2one("sedar.marine.port")
    tug_class_id = fields.Many2one("sedar.tug.class")
    pricing_basis = fields.Selection(PRICING_BASES, required=True, default="per_service")
    rate = fields.Monetary(required=True)
    minimum_charge = fields.Monetary()
    currency_id = fields.Many2one(
        "res.currency", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    valid_from = fields.Date(required=True, default=fields.Date.context_today)
    valid_until = fields.Date()
    approved = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    @api.depends("partner_id", "service_type_id", "port_id")
    def _compute_name(self):
        for tariff in self:
            parts = [tariff.partner_id.name, tariff.service_type_id.name]
            if tariff.port_id:
                parts.append(tariff.port_id.name)
            tariff.name = " - ".join(filter(None, parts))

    @api.constrains("valid_from", "valid_until", "rate", "minimum_charge")
    def _check_values(self):
        for tariff in self:
            if tariff.valid_until and tariff.valid_until < tariff.valid_from:
                raise ValidationError("Tariff end date cannot be earlier than its start date.")
            if tariff.rate < 0 or tariff.minimum_charge < 0:
                raise ValidationError("Tariff amounts cannot be negative.")

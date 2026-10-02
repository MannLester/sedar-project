from odoo import api, fields, models
from odoo.exceptions import ValidationError
from .marine_operation_common import _validate_operation_tug_links


class SedarMarineOperationLog(models.Model):
    _name = "sedar.marine.operation.log"
    _description = "Marine Operation Log"
    _order = "event_time, id"
    _check_company_auto = True

    operation_id = fields.Many2one(
        "sedar.marine.operation", required=True, ondelete="cascade", check_company=True,
    )
    company_id = fields.Many2one(related="operation_id.company_id", store=True, index=True)
    operation_tug_id = fields.Many2one(
        "sedar.marine.operation.tug", ondelete="set null", check_company=True,
    )
    event_time = fields.Datetime(required=True, default=fields.Datetime.now)
    event_type = fields.Selection([
        ("dispatched", "Operation Dispatched"),
        ("tug_departed", "Tug Departed Base"),
        ("arrived_on_scene", "Arrived on Scene"),
        ("towline_connected", "Towline Connected"),
        ("service_started", "Service Started"),
        ("vessel_moved", "Vessel Movement Started"),
        ("vessel_positioned", "Vessel Berthed / Positioned"),
        ("towline_released", "Towline Released"),
        ("tugs_returned", "Tugs Returned"),
        ("service_completed", "Service Completed"),
        ("general", "General Update"),
    ], required=True, default="general")
    berth_id = fields.Many2one("sedar.marine.berth")
    description = fields.Text(required=True)
    recorded_by = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    client_visible = fields.Boolean(default=False)
    attachment = fields.Binary(attachment=True)
    attachment_filename = fields.Char()

    @api.constrains("operation_id", "operation_tug_id")
    def _check_operation_tug(self):
        _validate_operation_tug_links(self)


class SedarMarineOperationDelay(models.Model):
    _name = "sedar.marine.operation.delay"
    _description = "Marine Operation Delay"
    _order = "start_time desc"
    _check_company_auto = True

    operation_id = fields.Many2one(
        "sedar.marine.operation", required=True, ondelete="cascade", check_company=True,
    )
    company_id = fields.Many2one(related="operation_id.company_id", store=True, index=True)
    operation_tug_id = fields.Many2one(
        "sedar.marine.operation.tug", ondelete="set null", check_company=True,
    )
    category = fields.Selection([
        ("weather", "Weather"), ("client", "Client Delay"),
        ("port", "Port Congestion"), ("mechanical", "Mechanical Issue"),
        ("crew", "Crew Issue"), ("safety", "Safety Hold"), ("other", "Other"),
    ], required=True)
    responsible_party = fields.Selection([
        ("sedar", "SEDAR"), ("client", "Client"), ("port", "Port / Authority"),
        ("third_party", "Third Party"), ("force_majeure", "Force Majeure"),
    ], required=True)
    start_time = fields.Datetime(required=True)
    end_time = fields.Datetime()
    duration_hours = fields.Float(compute="_compute_duration", store=True)
    description = fields.Text(required=True)
    state = fields.Selection([
        ("open", "Open"), ("resolved", "Resolved"),
    ], required=True, default="open")
    client_visible = fields.Boolean(default=False)

    @api.depends("start_time", "end_time")
    def _compute_duration(self):
        for delay in self:
            if delay.start_time and delay.end_time:
                delay.duration_hours = (delay.end_time - delay.start_time).total_seconds() / 3600.0
            else:
                delay.duration_hours = 0.0

    @api.constrains("start_time", "end_time")
    def _check_times(self):
        for delay in self:
            if delay.end_time and delay.end_time < delay.start_time:
                raise ValidationError("Delay end time cannot be earlier than its start time.")

    @api.constrains("operation_id", "operation_tug_id")
    def _check_operation_tug(self):
        _validate_operation_tug_links(self)

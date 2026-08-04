import math

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .marine_master import PRICING_BASES


class SedarMarineServiceOrder(models.Model):
    _name = "sedar.marine.service.order"
    _description = "Marine Service Order"
    _inherit = ["portal.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "requested_start desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    client_id = fields.Many2one("res.partner", required=True, tracking=True, ondelete="restrict")
    contact_id = fields.Many2one("res.partner", string="Requesting Contact")
    request_channel = fields.Selection([
        ("portal", "Client Portal"), ("phone", "Phone"),
        ("email", "Email"), ("walk_in", "Walk-in"),
        ("internal", "Internal"), ("other", "Other"),
    ], required=True, default="internal", tracking=True)
    client_reference = fields.Char(string="Client Reference / PO No.")
    priority = fields.Selection([
        ("normal", "Normal"), ("urgent", "Urgent"), ("emergency", "Emergency")
    ], default="normal", required=True, tracking=True)

    assisted_vessel_id = fields.Many2one("sedar.client.vessel", string="Assisted Vessel")
    assisted_vessel_name = fields.Char(required=True)
    service_type_id = fields.Many2one("sedar.marine.service.type", required=True, tracking=True)
    service_subtype = fields.Char()
    number_of_tugs = fields.Integer(default=1, required=True)
    tug_class_id = fields.Many2one("sedar.tug.class", string="Requested Tug Class")
    required_bollard_pull = fields.Float(string="Required Bollard Pull (T)")
    scope_of_work = fields.Text(required=True)
    special_instructions = fields.Text()

    port_id = fields.Many2one("sedar.marine.port", string="Port / Operating Area", required=True)
    origin_berth_id = fields.Many2one("sedar.marine.berth", string="Starting Berth / Location")
    destination_berth_id = fields.Many2one("sedar.marine.berth", string="Destination Berth / Location")
    requested_start = fields.Datetime(required=True, tracking=True)
    estimated_duration_hours = fields.Float(string="Estimated Duration (Hours)", default=1.0)
    requested_completion = fields.Datetime(compute="_compute_requested_completion", store=True)

    hazardous_cargo = fields.Boolean()
    cargo_description = fields.Char()
    permit_required = fields.Boolean()
    safety_requirements = fields.Text()
    supporting_document = fields.Binary(attachment=True)
    supporting_document_filename = fields.Char()

    tariff_id = fields.Many2one("sedar.client.tariff", readonly=True, copy=False)
    pricing_basis = fields.Selection(PRICING_BASES, readonly=True, copy=False)
    pricing_status = fields.Selection([
        ("resolved", "Tariff Resolved"),
        ("review", "Pricing Review Required"),
        ("manual", "Manual Quotation"),
    ], default="review", required=True, readonly=True, tracking=True)
    price_source = fields.Selection([
        ("client_tariff", "Client Tariff"),
        ("standard_tariff", "Standard Tariff"),
        ("manual", "Manual"),
    ], readonly=True, copy=False)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    unit_rate = fields.Monetary(readonly=True, copy=False)
    minimum_charge = fields.Monetary(readonly=True, copy=False)
    pricing_quantity = fields.Float(compute="_compute_pricing", store=True)
    estimated_amount = fields.Monetary(compute="_compute_pricing", store=True)

    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"),
        ("review", "Under Review"), ("needs_info", "Needs Client Information"),
        ("pricing", "Pricing Review"), ("quoted", "Quoted"),
        ("confirmed", "Client Confirmed"), ("planning", "Operations Planning"),
        ("blocked", "Blocked"), ("ready", "Ready"),
        ("dispatched", "Dispatched"), ("in_progress", "In Progress"),
        ("completed", "Completed"), ("billing_ready", "Billing Ready"),
        ("closed", "Closed"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, tracking=True)
    cancellation_reason = fields.Text()
    tug_assignment_ids = fields.One2many("sedar.tug.assignment", "order_id", string="Tug Assignments")
    tug_assignment_count = fields.Integer(compute="_compute_readiness", store=True)
    readiness_status = fields.Selection([
        ("not_planned", "Not Yet Planned"),
        ("waiting_tug", "Waiting for Tug"),
        ("waiting_crew", "Waiting for Crew Plan"),
        ("blocked_tug", "Blocked by Tug Availability"),
        ("blocked_crew", "Blocked by Crew or Compliance"),
        ("waiting_inventory", "Waiting for Inventory"),
        ("ready", "Ready"),
    ], compute="_compute_readiness", store=True)
    readiness_reason = fields.Char(compute="_compute_readiness", store=True)
    inventory_ready = fields.Boolean(
        string="Inventory Ready",
        tracking=True,
        help="Temporary manual confirmation. This control will be revamped and replaced by the dedicated Inventory module.",
    )
    inventory_ready_by_id = fields.Many2one(
        "res.users", string="Inventory Confirmed By", readonly=True, copy=False
    )
    inventory_ready_at = fields.Datetime(
        string="Inventory Confirmed At", readonly=True, copy=False
    )
    tug_completion_count = fields.Integer(compute="_compute_tug_completion", store=True)
    all_tugs_complete = fields.Boolean(compute="_compute_tug_completion", store=True)

    @api.depends("number_of_tugs", "tug_assignment_ids.state", "tug_assignment_ids.completion_state")
    def _compute_tug_completion(self):
        for order in self:
            assignments = order.tug_assignment_ids.filtered(lambda assignment: assignment.state != "cancelled")
            completed = assignments.filtered(lambda assignment: assignment.completion_state == "submitted")
            order.tug_completion_count = len(completed)
            order.all_tugs_complete = bool(
                len(assignments) >= order.number_of_tugs and len(completed) == len(assignments)
            )

    def _sync_completion_from_tugs(self):
        """Keep operational completion aligned with every active tug declaration."""
        for order in self:
            assignments = order.tug_assignment_ids.filtered(lambda assignment: assignment.state != "cancelled")
            all_complete = bool(
                len(assignments) >= order.number_of_tugs
                and all(line.completion_state == "submitted" for line in assignments)
            )
            if all_complete and order.state in {"dispatched", "in_progress"}:
                order.write({"state": "completed"})
            elif not all_complete and order.state in {"completed", "billing_ready"}:
                order.write({"state": "in_progress"})

    @api.depends(
        "state", "number_of_tugs", "tug_assignment_ids.state",
        "tug_assignment_ids.tugboat_id.availability_status",
        "tug_assignment_ids.requirement_ids.required_count",
        "tug_assignment_ids.requirement_ids.crew_assignment_ids.state",
        "tug_assignment_ids.requirement_ids.gap_count",
        "tug_assignment_ids.requirement_ids.compliance_issue_count",
        "inventory_ready",
    )
    def _compute_readiness(self):
        for order in self:
            assignments = order.tug_assignment_ids.filtered(lambda assignment: assignment.state != "cancelled")
            order.tug_assignment_count = len(assignments)
            if not assignments:
                if order.state in {"draft", "submitted", "review", "needs_info", "pricing", "quoted"}:
                    order.readiness_status = "not_planned"
                    order.readiness_reason = "Order has not reached operations planning."
                else:
                    order.readiness_status = "waiting_tug"
                    order.readiness_reason = "No tugboat has been assigned."
                continue
            if len(assignments) < order.number_of_tugs:
                order.readiness_status = "waiting_tug"
                order.readiness_reason = "%s of %s requested tugboats are assigned." % (
                    len(assignments), order.number_of_tugs,
                )
                continue
            unavailable = assignments.filtered(lambda assignment: not assignment.tug_available)
            if unavailable:
                order.readiness_status = "blocked_tug"
                order.readiness_reason = "Unavailable tugboat: %s" % ", ".join(unavailable.mapped("tugboat_id.name"))
                continue
            requirements = assignments.mapped("requirement_ids")
            if not requirements:
                order.readiness_status = "waiting_crew"
                order.readiness_reason = "Manning requirements have not been generated."
                continue
            compliance = requirements.filtered(lambda requirement: requirement.compliance_issue_count)
            shortages = requirements.filtered(lambda requirement: requirement.gap_count)
            if compliance:
                order.readiness_status = "blocked_crew"
                order.readiness_reason = "Crew certificate, medical, leave, rank, or schedule issue."
            elif shortages:
                ranks = ", ".join(shortages.mapped("rank_id.name"))
                order.readiness_status = "blocked_crew"
                order.readiness_reason = "Unfilled manning requirement: %s" % ranks
            elif not order.inventory_ready:
                order.readiness_status = "waiting_inventory"
                order.readiness_reason = "Inventory readiness has not been confirmed."
            else:
                order.readiness_status = "ready"
                order.readiness_reason = "Tugboat, minimum compliant crew, and inventory are ready."

    @api.depends("requested_start", "estimated_duration_hours")
    def _compute_requested_completion(self):
        for order in self:
            if order.requested_start and order.estimated_duration_hours > 0:
                order.requested_completion = fields.Datetime.add(
                    order.requested_start, hours=order.estimated_duration_hours
                )
            else:
                order.requested_completion = False

    @api.depends(
        "pricing_basis", "unit_rate", "minimum_charge",
        "number_of_tugs", "estimated_duration_hours"
    )
    def _compute_pricing(self):
        for order in self:
            basis = order.pricing_basis
            if basis == "per_service":
                quantity = 1.0
            elif basis == "per_tug":
                quantity = order.number_of_tugs
            elif basis == "per_hour":
                quantity = order.estimated_duration_hours
            elif basis == "per_tug_hour":
                quantity = order.estimated_duration_hours * order.number_of_tugs
            elif basis == "per_day":
                quantity = max(1, math.ceil(order.estimated_duration_hours / 24.0))
            else:
                quantity = 0.0
            order.pricing_quantity = quantity
            calculated = order.unit_rate * quantity
            order.estimated_amount = max(calculated, order.minimum_charge) if quantity else 0.0

    @api.onchange("assisted_vessel_id")
    def _onchange_assisted_vessel(self):
        if self.assisted_vessel_id:
            self.assisted_vessel_name = self.assisted_vessel_id.name

    @api.onchange("client_id", "service_type_id", "port_id", "tug_class_id", "requested_start")
    def _onchange_tariff_inputs(self):
        self._apply_tariff()

    def _find_tariff(self):
        self.ensure_one()
        if not self.client_id or not self.service_type_id:
            return self.env["sedar.client.tariff"]
        tariff_date = fields.Date.to_date(self.requested_start) or fields.Date.context_today(self)
        domain = [
            ("partner_id", "=", self.client_id.commercial_partner_id.id),
            ("service_type_id", "=", self.service_type_id.id),
            ("approved", "=", True), ("active", "=", True),
            ("valid_from", "<=", tariff_date),
            "|", ("valid_until", "=", False), ("valid_until", ">=", tariff_date),
        ]
        tariffs = self.env["sedar.client.tariff"].search(domain, order="valid_from desc, id desc")
        exact = tariffs.filtered(
            lambda tariff: (not tariff.port_id or tariff.port_id == self.port_id)
            and (not tariff.tug_class_id or tariff.tug_class_id == self.tug_class_id)
        )
        return exact[:1]

    def _apply_tariff(self):
        for order in self:
            tariff = order._find_tariff()
            if tariff:
                order.update({
                    "tariff_id": tariff.id,
                    "pricing_basis": tariff.pricing_basis,
                    "pricing_status": "manual" if tariff.pricing_basis == "quotation" else "resolved",
                    "price_source": "client_tariff",
                    "currency_id": tariff.currency_id.id,
                    "unit_rate": tariff.rate,
                    "minimum_charge": tariff.minimum_charge,
                })
            elif order.service_type_id and order.service_type_id.standard_rate > 0:
                service = order.service_type_id
                order.update({
                    "tariff_id": False,
                    "pricing_basis": service.pricing_basis,
                    "pricing_status": "manual" if service.pricing_basis == "quotation" else "resolved",
                    "price_source": "standard_tariff",
                    "currency_id": service.currency_id.id,
                    "unit_rate": service.standard_rate,
                    "minimum_charge": 0,
                })
            else:
                order.update({
                    "tariff_id": False, "pricing_basis": "quotation",
                    "pricing_status": "review", "price_source": "manual",
                    "unit_rate": 0, "minimum_charge": 0,
                })

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if order.name == "New":
                order.name = self.env["ir.sequence"].next_by_code("sedar.marine.service.order") or "New"
            order._apply_tariff()
        return orders

    def write(self, vals):
        inventory_inputs = {
            "service_type_id", "number_of_tugs", "tug_class_id", "required_bollard_pull",
            "scope_of_work", "special_instructions", "port_id", "origin_berth_id",
            "destination_berth_id", "requested_start", "estimated_duration_hours",
            "hazardous_cargo", "cargo_description", "permit_required", "safety_requirements",
        }
        if inventory_inputs.intersection(vals) and not self.env.context.get("sedar_readiness_sync"):
            vals = dict(vals, inventory_ready=False, inventory_ready_by_id=False, inventory_ready_at=False)
        return super().write(vals)

    @api.constrains("number_of_tugs", "estimated_duration_hours", "requested_start")
    def _check_operational_values(self):
        for order in self:
            if order.number_of_tugs < 1:
                raise ValidationError("At least one tug must be requested.")
            if order.estimated_duration_hours <= 0:
                raise ValidationError("Estimated duration must be greater than zero.")

    def action_submit(self):
        self._apply_tariff()
        self.write({"state": "submitted"})

    def action_review(self):
        self.write({"state": "review"})

    def action_request_info(self):
        self.write({"state": "needs_info"})

    def action_quote(self):
        self.write({"state": "quoted"})

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_plan(self):
        self.write({"state": "planning"})

    def action_confirm_inventory_ready(self):
        self._check_operations_manager()
        self.with_context(sedar_readiness_sync=True).write({
            "inventory_ready": True,
            "inventory_ready_by_id": self.env.user.id,
            "inventory_ready_at": fields.Datetime.now(),
        })
        return True

    def _check_operations_manager(self):
        if not self.env.su and not self.env.user.has_group("sedar_marine_operations.group_operations_manager"):
            raise AccessError("Only an Operations Manager may advance an order through dispatch.")

    def action_mark_ready(self):
        self._check_operations_manager()
        for order in self:
            if order.state not in {"planning", "blocked"}:
                raise UserError("Only a planned or blocked order can be marked ready.")
            if order.readiness_status != "ready":
                raise UserError(order.readiness_reason or "Tug and crew readiness is incomplete.")
        self.write({"state": "ready"})
        return True

    def action_dispatch(self):
        self._check_operations_manager()
        for order in self:
            if order.state != "ready" or order.readiness_status != "ready":
                raise UserError("Only a ready Service Order can be dispatched.")
            active_tugs = order.tug_assignment_ids.filtered(lambda assignment: assignment.state != "cancelled")
            active_tugs.write({"state": "confirmed"})
            active_tugs.mapped("requirement_ids.crew_assignment_ids").filtered(
                lambda crew: crew.state == "planned"
            ).write({"state": "confirmed"})
        self.write({"state": "dispatched"})
        return True

    def action_start_service(self):
        self._check_operations_manager()
        if any(order.state != "dispatched" for order in self):
            raise UserError("Only a dispatched Service Order can be started.")
        self.write({"state": "in_progress"})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = f"/my/sedar/orders/{order.id}"

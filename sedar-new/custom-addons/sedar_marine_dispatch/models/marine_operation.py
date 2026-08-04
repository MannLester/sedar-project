from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


OPERATION_STATES = [
    ("draft", "Ready to Dispatch"),
    ("dispatched", "Dispatched"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]


class SedarMarineOperation(models.Model):
    _name = "sedar.marine.operation"
    _description = "Marine Service Operation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    order_id = fields.Many2one(
        "sedar.marine.service.order", required=True, ondelete="restrict", index=True,
    )
    client_id = fields.Many2one(related="order_id.client_id", store=True)
    assisted_vessel_id = fields.Many2one(related="order_id.assisted_vessel_id", store=True)
    service_type_id = fields.Many2one(related="order_id.service_type_id", store=True)
    port_id = fields.Many2one(related="order_id.port_id", store=True)
    planned_start = fields.Datetime(related="order_id.requested_start", store=True)
    planned_end = fields.Datetime(related="order_id.requested_completion", store=True)
    dispatcher_id = fields.Many2one("res.users", string="Dispatcher", tracking=True)
    state = fields.Selection(OPERATION_STATES, default="draft", required=True, tracking=True)
    dispatch_time = fields.Datetime(tracking=True)
    actual_start = fields.Datetime(tracking=True)
    actual_end = fields.Datetime(tracking=True)
    actual_duration_hours = fields.Float(compute="_compute_actual_duration", store=True)
    completion_summary = fields.Text()
    client_representative = fields.Char()
    client_confirmation_time = fields.Datetime()
    billing_ready = fields.Boolean(default=False, tracking=True)
    cancellation_reason = fields.Text()
    tug_operation_ids = fields.One2many("sedar.marine.operation.tug", "operation_id")
    log_ids = fields.One2many("sedar.marine.operation.log", "operation_id")
    delay_ids = fields.One2many("sedar.marine.operation.delay", "operation_id")
    attachment_ids = fields.Many2many("ir.attachment", string="Completion Evidence")

    _order_unique = models.Constraint(
        "UNIQUE(order_id)", "A service order can have only one marine operation."
    )

    @api.depends("actual_start", "actual_end")
    def _compute_actual_duration(self):
        for operation in self:
            if operation.actual_start and operation.actual_end:
                delta = operation.actual_end - operation.actual_start
                operation.actual_duration_hours = delta.total_seconds() / 3600.0
            else:
                operation.actual_duration_hours = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        operations = super().create(vals_list)
        for operation in operations:
            if operation.name == "New":
                operation.name = self.env["ir.sequence"].next_by_code("sedar.marine.operation") or "New"
            operation._refresh_dispatch_snapshot()
        return operations

    def _refresh_dispatch_snapshot(self):
        for operation in self:
            if operation.state != "draft":
                continue
            operation.tug_operation_ids.sudo().unlink()
            assignments = operation.order_id.tug_assignment_ids.filtered(
                lambda assignment: assignment.state != "cancelled"
            )
            for assignment in assignments:
                tug_operation = self.env["sedar.marine.operation.tug"].create({
                    "operation_id": operation.id,
                    "tug_assignment_id": assignment.id,
                    "tugboat_id": assignment.tugboat_id.id,
                })
                for crew_assignment in assignment.requirement_ids.mapped("crew_assignment_ids").filtered(
                    lambda item: item.state != "rejected"
                ):
                    self.env["sedar.marine.operation.crew"].create({
                        "operation_tug_id": tug_operation.id,
                        "crew_assignment_id": crew_assignment.id,
                        "crew_profile_id": crew_assignment.crew_profile_id.id,
                        "employee_id": crew_assignment.employee_id.id,
                        "employee_name": crew_assignment.employee_id.name,
                        "rank_id": crew_assignment.rank_id.id,
                        "certificate_clearance": crew_assignment.is_eligible,
                        "clearance_notes": crew_assignment.eligibility_reason,
                    })

    def _ensure_dispatcher(self):
        if not self.env.user.has_group("sedar_marine_dispatch.group_dispatcher"):
            raise UserError("Only a Dispatcher or Dispatch Manager can perform this action.")

    def _ensure_manager(self):
        if not self.env.user.has_group("sedar_marine_dispatch.group_dispatch_manager"):
            raise UserError("Only a Dispatch Manager can perform this action.")

    def _ensure_dispatchable(self):
        for operation in self:
            order = operation.order_id
            if operation.state != "draft":
                raise UserError("Only draft operations can be dispatched.")
            operation._refresh_dispatch_snapshot()
            if order.readiness_status != "ready":
                raise UserError("This operation cannot be dispatched: %s" % order.readiness_reason)
            if len(operation.tug_operation_ids) != order.number_of_tugs:
                raise UserError("The number of planned tugs does not match the service order.")
            if any(not tug.tugboat_id.active for tug in operation.tug_operation_ids):
                raise UserError("An assigned tugboat is inactive.")
            if any(not tug.tugboat_id.availability_status in {"available", "assigned"}
                   for tug in operation.tug_operation_ids):
                raise UserError("An assigned tugboat is not available.")
            if any(not crew.certificate_clearance for crew in operation.tug_operation_ids.mapped("crew_manifest_ids")):
                raise UserError("The crew manifest contains an ineligible employee.")
            active_operations = self.env["sedar.marine.operation"].search([
                ("id", "!=", operation.id),
                ("state", "in", ["dispatched", "in_progress"]),
                ("planned_start", "<", operation.planned_end),
                ("planned_end", ">", operation.planned_start),
            ])
            occupied_tugs = active_operations.mapped("tug_operation_ids.tugboat_id")
            conflict_tugs = operation.tug_operation_ids.mapped("tugboat_id") & occupied_tugs
            if conflict_tugs:
                raise UserError("A tugboat is already assigned to an overlapping operation: %s" %
                                ", ".join(conflict_tugs.mapped("name")))

    def action_dispatch(self):
        self._ensure_dispatcher()
        self._ensure_dispatchable()
        now = fields.Datetime.now()
        for operation in self:
            operation.order_id.tug_assignment_ids.filtered(
                lambda assignment: assignment.state != "cancelled"
            ).write({"state": "confirmed"})
            operation.order_id.tug_assignment_ids.mapped("requirement_ids").mapped(
                "crew_assignment_ids"
            ).filtered(lambda assignment: assignment.state != "rejected").write({"state": "confirmed"})
            operation.tug_operation_ids.mapped("tugboat_id").filtered(
                lambda tug: tug.availability_status == "available"
            ).write({"availability_status": "assigned"})
            operation.tug_operation_ids.mapped("crew_manifest_ids.crew_profile_id").filtered(
                lambda profile: profile.availability_status == "available"
            ).write({"availability_status": "assigned"})
            operation.write({"state": "dispatched", "dispatch_time": now, "dispatcher_id": self.env.user.id})
            operation.order_id.write({"state": "dispatched"})
            self.env["sedar.marine.operation.log"].create({
                "operation_id": operation.id, "event_time": now,
                "event_type": "dispatched", "description": "Operation dispatched.",
            })
        return True

    def action_start(self):
        self._ensure_dispatcher()
        for operation in self:
            if operation.state != "dispatched":
                raise UserError("Only dispatched operations can be started.")
            now = fields.Datetime.now()
            operation.write({"state": "in_progress", "actual_start": now})
            operation.order_id.write({"state": "in_progress"})
            self.env["sedar.marine.operation.log"].create({
                "operation_id": operation.id, "event_time": now,
                "event_type": "service_started", "description": "Service execution started.",
            })
        return True

    def action_return_tugs(self):
        self._ensure_dispatcher()
        for operation in self:
            if operation.state not in {"dispatched", "in_progress"}:
                raise UserError("Only active operations can return tugboats.")
            now = fields.Datetime.now()
            operation.tug_operation_ids.filtered(
                lambda tug: tug.state != "returned"
            ).write({"state": "returned", "returned_base_at": now})
            self.env["sedar.marine.operation.log"].create({
                "operation_id": operation.id, "event_time": now,
                "event_type": "tugs_returned", "description": "Participating tugboats returned.",
            })
        return True

    def action_complete(self):
        self._ensure_manager()
        for operation in self:
            if operation.state != "in_progress":
                raise UserError("Only in-progress operations can be completed.")
            if not operation.actual_start:
                raise UserError("Record the actual start before completing the operation.")
            if not operation.completion_summary:
                raise UserError("Enter a completion summary before completing the operation.")
            if any(tug.state != "returned" for tug in operation.tug_operation_ids):
                raise UserError("Return all participating tugboats before completing the operation.")
            now = fields.Datetime.now()
            operation.write({"state": "completed", "actual_end": now})
            operation.order_id.write({"state": "completed"})
            operation.tug_operation_ids.mapped("tugboat_id").filtered(
                lambda tug: tug.availability_status == "assigned"
            ).write({"availability_status": "available"})
            operation.tug_operation_ids.mapped("crew_manifest_ids.crew_profile_id").filtered(
                lambda profile: profile.availability_status == "assigned"
            ).write({"availability_status": "available"})
            self.env["sedar.marine.operation.log"].create({
                "operation_id": operation.id, "event_time": now,
                "event_type": "service_completed", "description": "Service execution completed.",
            })
        return True

    def action_mark_billing_ready(self):
        self._ensure_manager()
        for operation in self:
            if operation.state != "completed":
                raise UserError("Only completed operations can be marked billing ready.")
            operation.write({"billing_ready": True})
            operation.order_id.write({"state": "billing_ready"})
        return True

    def action_cancel(self):
        self._ensure_dispatcher()
        for operation in self:
            if operation.state in {"completed", "cancelled"}:
                raise UserError("Completed or already cancelled operations cannot be cancelled.")
            if not operation.cancellation_reason:
                raise UserError("Enter a cancellation reason first.")
            operation.write({"state": "cancelled"})
            operation.order_id.write({"state": "cancelled", "cancellation_reason": operation.cancellation_reason})
            operation.tug_operation_ids.mapped("tugboat_id").filtered(
                lambda tug: tug.availability_status == "assigned"
            ).write({"availability_status": "available"})
            operation.tug_operation_ids.mapped("crew_manifest_ids.crew_profile_id").filtered(
                lambda profile: profile.availability_status == "assigned"
            ).write({"availability_status": "available"})
        return True

    def action_open_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Service Order",
            "res_model": "sedar.marine.service.order",
            "res_id": self.order_id.id,
            "view_mode": "form",
        }

    @api.constrains("actual_start", "actual_end")
    def _check_actual_times(self):
        for operation in self:
            if operation.actual_start and operation.actual_end and operation.actual_end < operation.actual_start:
                raise ValidationError("Actual completion cannot be earlier than actual start.")


class SedarTugAssignmentDispatchLock(models.Model):
    _inherit = "sedar.tug.assignment"

    def write(self, vals):
        locked = self.filtered(lambda assignment: assignment.order_id.state in {
            "dispatched", "in_progress", "completed", "billing_ready"
        })
        if locked:
            raise UserError("Tug planning is locked after dispatch.")
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda assignment: assignment.order_id.state in {
            "dispatched", "in_progress", "completed", "billing_ready"
        }):
            raise UserError("Tug planning is locked after dispatch.")
        return super().unlink()


class SedarCrewAssignmentDispatchLock(models.Model):
    _inherit = "sedar.crew.assignment"

    def write(self, vals):
        locked = self.filtered(lambda assignment: assignment.order_id.state in {
            "dispatched", "in_progress", "completed", "billing_ready"
        })
        if locked:
            raise UserError("Crew planning is locked after dispatch.")
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda assignment: assignment.order_id.state in {
            "dispatched", "in_progress", "completed", "billing_ready"
        }):
            raise UserError("Crew planning is locked after dispatch.")
        return super().unlink()


class SedarMarineOperationTug(models.Model):
    _name = "sedar.marine.operation.tug"
    _description = "Operation Tug"
    _order = "tugboat_id"

    operation_id = fields.Many2one("sedar.marine.operation", required=True, ondelete="cascade")
    tug_assignment_id = fields.Many2one("sedar.tug.assignment", required=True, ondelete="restrict")
    tugboat_id = fields.Many2one("sedar.tugboat", required=True, ondelete="restrict")
    state = fields.Selection([
        ("pending", "Pending"), ("dispatched", "Dispatched"),
        ("on_scene", "On Scene"), ("released", "Released"), ("returned", "Returned"),
    ], default="pending", required=True)
    departed_base_at = fields.Datetime()
    arrived_on_scene_at = fields.Datetime()
    service_released_at = fields.Datetime()
    returned_base_at = fields.Datetime()
    remarks = fields.Text()
    crew_manifest_ids = fields.One2many("sedar.marine.operation.crew", "operation_tug_id")

    def action_mark_on_scene(self):
        for tug in self:
            tug.write({"state": "on_scene", "arrived_on_scene_at": fields.Datetime.now()})

    def action_release(self):
        for tug in self:
            tug.write({"state": "released", "service_released_at": fields.Datetime.now()})


class SedarMarineOperationCrew(models.Model):
    _name = "sedar.marine.operation.crew"
    _description = "Operation Crew Manifest"
    _order = "rank_id, employee_name"

    operation_tug_id = fields.Many2one("sedar.marine.operation.tug", required=True, ondelete="cascade")
    crew_assignment_id = fields.Many2one("sedar.crew.assignment", ondelete="restrict")
    crew_profile_id = fields.Many2one("sedar.crew.profile", required=True, ondelete="restrict")
    employee_id = fields.Many2one("hr.employee", ondelete="restrict")
    employee_name = fields.Char(required=True)
    rank_id = fields.Many2one("sedar.crew.rank", ondelete="restrict")
    certificate_clearance = fields.Boolean()
    clearance_notes = fields.Char()
    duty_status = fields.Selection([
        ("assigned", "Assigned"), ("on_duty", "On Duty"),
        ("released", "Released"), ("replaced", "Replaced"),
    ], default="assigned", required=True)


class SedarMarineOperationLog(models.Model):
    _name = "sedar.marine.operation.log"
    _description = "Marine Operation Log"
    _order = "event_time, id"

    operation_id = fields.Many2one("sedar.marine.operation", required=True, ondelete="cascade")
    operation_tug_id = fields.Many2one("sedar.marine.operation.tug", ondelete="set null")
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


class SedarMarineOperationDelay(models.Model):
    _name = "sedar.marine.operation.delay"
    _description = "Marine Operation Delay"
    _order = "start_time desc"

    operation_id = fields.Many2one("sedar.marine.operation", required=True, ondelete="cascade")
    operation_tug_id = fields.Many2one("sedar.marine.operation.tug", ondelete="set null")
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

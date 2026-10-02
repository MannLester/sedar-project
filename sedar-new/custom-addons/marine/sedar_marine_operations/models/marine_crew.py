from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarTugboat(models.Model):
    _name = "sedar.tugboat"
    _description = "SEDAR Tugboat"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        copy=False,
    )
    registration_number = fields.Char(required=True, index=True)
    call_sign = fields.Char()
    mmsi = fields.Char(string="MMSI")
    tug_class_id = fields.Many2one("sedar.tug.class", required=True, ondelete="restrict")
    bollard_pull = fields.Float(string="Bollard Pull (T)")
    fuel_capacity = fields.Float(string="Fuel Capacity (L)")
    home_port_id = fields.Many2one("sedar.marine.port")
    availability_status = fields.Selection([
        ("available", "Available"),
        ("assigned", "Assigned"),
        ("maintenance", "Maintenance Hold"),
        ("inactive", "Inactive"),
    ], required=True, default="available")
    home_crew_ids = fields.One2many("sedar.crew.profile", "home_tugboat_id", string="Home Crew")
    active = fields.Boolean(default=True)

    _registration_unique = models.Constraint(
        "UNIQUE(registration_number)", "Tugboat registration number must be unique."
    )

    def write(self, vals):
        if "company_id" in vals and any(
            tugboat.company_id.id != vals["company_id"] for tugboat in self
        ):
            raise ValidationError("A Tugboat's company cannot be changed after creation.")
        return super().write(vals)


class SedarCrewRank(models.Model):
    _name = "sedar.crew.rank"
    _description = "Marine Crew Rank"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Crew rank code must be unique.")


class SedarCrewCertificateType(models.Model):
    _name = "sedar.crew.certificate.type"
    _description = "Crew Certificate Type"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Certificate type code must be unique.")


class SedarCrewProfile(models.Model):
    _name = "sedar.crew.profile"
    _description = "SEDAR Crew Profile"
    _rec_name = "employee_id"
    _order = "rank_id, employee_id"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", index=True)
    employee_number = fields.Char(required=True, index=True)
    rank_id = fields.Many2one("sedar.crew.rank", required=True, ondelete="restrict")
    home_tugboat_id = fields.Many2one("sedar.tugboat", string="Home Tugboat")
    seafarer_number = fields.Char()
    availability_status = fields.Selection([
        ("available", "Available"),
        ("assigned", "Assigned"),
        ("leave", "On Leave"),
        ("unavailable", "Unavailable"),
    ], required=True, default="available")
    certificate_ids = fields.One2many("sedar.crew.certificate", "crew_profile_id")
    active = fields.Boolean(default=True)

    _employee_unique = models.Constraint("UNIQUE(employee_id)", "An employee can have only one crew profile.")
    _employee_number_unique = models.Constraint("UNIQUE(employee_number)", "Crew employee number must be unique.")


class SedarCrewCertificate(models.Model):
    _name = "sedar.crew.certificate"
    _description = "Crew Certificate or Medical Record"
    _order = "expiry_date, crew_profile_id"

    crew_profile_id = fields.Many2one("sedar.crew.profile", required=True, ondelete="cascade")
    certificate_type_id = fields.Many2one("sedar.crew.certificate.type", required=True, ondelete="restrict")
    certificate_number = fields.Char(required=True)
    issue_date = fields.Date()
    expiry_date = fields.Date(required=True)
    status = fields.Selection([
        ("valid", "Valid"), ("expiring", "Expiring Soon"), ("expired", "Expired")
    ], compute="_compute_status")
    attachment = fields.Binary(attachment=True)
    attachment_filename = fields.Char()

    @api.depends("expiry_date")
    def _compute_status(self):
        today = fields.Date.context_today(self)
        warning_date = fields.Date.add(today, days=30)
        for certificate in self:
            if certificate.expiry_date < today:
                certificate.status = "expired"
            elif certificate.expiry_date <= warning_date:
                certificate.status = "expiring"
            else:
                certificate.status = "valid"


class SedarManningTemplate(models.Model):
    _name = "sedar.manning.template"
    _description = "Service Manning Template"
    _order = "name"

    name = fields.Char(required=True)
    service_type_id = fields.Many2one("sedar.marine.service.type", required=True, ondelete="cascade")
    tug_class_id = fields.Many2one("sedar.tug.class")
    line_ids = fields.One2many("sedar.manning.template.line", "template_id")
    active = fields.Boolean(default=True)


class SedarManningTemplateLine(models.Model):
    _name = "sedar.manning.template.line"
    _description = "Manning Template Requirement"
    _order = "sequence, rank_id"

    template_id = fields.Many2one("sedar.manning.template", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    rank_id = fields.Many2one("sedar.crew.rank", required=True, ondelete="restrict")
    required_count = fields.Integer(required=True, default=1)
    required_certificate_type_ids = fields.Many2many("sedar.crew.certificate.type")

    @api.constrains("required_count")
    def _check_required_count(self):
        if any(line.required_count < 1 for line in self):
            raise ValidationError("Manning requirement count must be at least one.")


class SedarTugAssignment(models.Model):
    _name = "sedar.tug.assignment"
    _description = "Service Order Tug Assignment"
    _order = "planned_start, tugboat_id"
    _check_company_auto = True

    order_id = fields.Many2one(
        "sedar.marine.service.order", required=True, ondelete="cascade", check_company=True,
    )
    company_id = fields.Many2one(related="order_id.company_id", store=True, index=True)
    order_state = fields.Selection(related="order_id.state", string="Service Order Status")
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, ondelete="restrict", check_company=True,
    )
    planned_start = fields.Datetime(related="order_id.requested_start", store=True)
    planned_end = fields.Datetime(related="order_id.requested_completion", store=True)
    state = fields.Selection([
        ("planned", "Planned"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")
    ], required=True, default="planned")
    tug_available = fields.Boolean(compute="_compute_tug_available", store=True)
    availability_reason = fields.Char(compute="_compute_tug_available", store=True)
    requirement_ids = fields.One2many("sedar.manning.requirement", "tug_assignment_id")
    tug_master_profile_id = fields.Many2one(
        "sedar.crew.profile", string="Tug Master", compute="_compute_tug_master", store=True
    )
    tug_master_user_id = fields.Many2one(
        "res.users", string="Tug Master User", compute="_compute_tug_master", store=True
    )
    completion_state = fields.Selection([
        ("pending", "Pending"),
        ("submitted", "Declared Complete"),
        ("returned", "Returned for Correction"),
    ], required=True, default="pending", copy=False)
    actual_start = fields.Datetime(copy=False)
    actual_end = fields.Datetime(copy=False)
    completion_note = fields.Text(copy=False)
    completion_evidence = fields.Binary(attachment=True, copy=False)
    completion_evidence_filename = fields.Char(copy=False)
    completion_declared_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    completion_declared_at = fields.Datetime(readonly=True, copy=False)
    completion_return_reason = fields.Text(copy=False)

    @api.depends(
        "requirement_ids.crew_assignment_ids.state",
        "requirement_ids.crew_assignment_ids.crew_profile_id.rank_id.code",
        "requirement_ids.crew_assignment_ids.crew_profile_id.employee_id.user_id",
    )
    def _compute_tug_master(self):
        for assignment in self:
            masters = assignment.requirement_ids.mapped("crew_assignment_ids").filtered(
                lambda crew: crew.state != "rejected" and crew.rank_id.code == "MASTER"
            )
            master = masters[:1].crew_profile_id
            assignment.tug_master_profile_id = master
            assignment.tug_master_user_id = master.employee_id.user_id

    @api.depends("tugboat_id.availability_status", "tugboat_id.active")
    def _compute_tug_available(self):
        for assignment in self:
            assignment.tug_available = bool(
                assignment.tugboat_id.active
                and assignment.tugboat_id.availability_status in {"available", "assigned"}
            )
            assignment.availability_reason = (
                False if assignment.tug_available
                else dict(assignment.tugboat_id._fields["availability_status"].selection).get(
                    assignment.tugboat_id.availability_status
                )
            )

    def action_generate_requirements(self):
        for assignment in self:
            if assignment.requirement_ids:
                continue
            template = self.env["sedar.manning.template"].search([
                ("service_type_id", "=", assignment.order_id.service_type_id.id),
                ("active", "=", True),
                "|", ("tug_class_id", "=", assignment.tugboat_id.tug_class_id.id),
                ("tug_class_id", "=", False),
            ], order="tug_class_id desc, id", limit=1)
            for line in template.line_ids:
                self.env["sedar.manning.requirement"].create({
                    "tug_assignment_id": assignment.id,
                    "rank_id": line.rank_id.id,
                    "required_count": line.required_count,
                    "required_certificate_type_ids": [fields.Command.set(line.required_certificate_type_ids.ids)],
                })

    @api.constrains("actual_start", "actual_end")
    def _check_actual_times(self):
        for assignment in self:
            if assignment.actual_start and assignment.actual_end and assignment.actual_end <= assignment.actual_start:
                raise ValidationError("Actual end time must be later than actual start time.")

    def _check_current_user_is_tug_master(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_marine_operations.group_tug_master"):
            raise AccessError("Only users with the Tug Master role can maintain tug completion records.")
        unauthorized = self.filtered(lambda assignment: assignment.tug_master_user_id != self.env.user)
        if unauthorized:
            raise AccessError("Only the assigned Tug Master can declare or resubmit completion for this tug.")

    def action_declare_complete(self):
        for assignment in self:
            assignment._check_current_user_is_tug_master()
            if assignment.state == "cancelled":
                raise UserError("A cancelled tug assignment cannot be completed.")
            if assignment.order_id.state not in {"dispatched", "in_progress", "completed"}:
                raise UserError("The service must be dispatched or in progress before completion can be declared.")
            if assignment.completion_state == "submitted":
                raise UserError("Completion has already been declared for this tug.")
            if not assignment.actual_start or not assignment.actual_end or not assignment.completion_note:
                raise UserError("Actual start, actual end, and a completion note are required.")
            assignment.with_context(sedar_completion_action=True).write({
                "completion_state": "submitted",
                "completion_declared_by_id": self.env.user.id,
                "completion_declared_at": fields.Datetime.now(),
                "completion_return_reason": False,
            })
        self.mapped("order_id").sync_completion_from_tugs()
        return True

    def action_return_completion(self):
        if not self.env.user.has_group("sedar_marine_operations.group_completion_reviewer"):
            raise AccessError("Only a Service Completion Reviewer can return a completion declaration.")
        for assignment in self:
            if assignment.completion_state != "submitted":
                raise UserError("Only a submitted completion can be returned.")
            if not assignment.completion_return_reason:
                raise UserError("Enter a correction reason before returning the completion.")
            assignment.with_context(sedar_completion_action=True).write({
                "completion_state": "returned",
                "completion_declared_by_id": False,
                "completion_declared_at": False,
            })
        self.mapped("order_id").sync_completion_from_tugs()
        return True

    def write(self, vals):
        if "order_id" in vals and any(
            assignment.order_id.id != vals["order_id"] for assignment in self
        ):
            raise ValidationError(
                "A Tug Assignment cannot move to another Service Order."
            )
        protected = {
            "actual_start", "actual_end", "completion_note", "completion_evidence",
            "completion_evidence_filename", "completion_state", "completion_declared_by_id",
            "completion_declared_at", "completion_return_reason",
        }
        if protected.intersection(vals) and not self.env.context.get("sedar_completion_action") and not self.env.su:
            manager_reason_only = (
                set(vals) <= {"completion_return_reason"}
                and self.env.user.has_group("sedar_marine_operations.group_completion_reviewer")
                and all(assignment.completion_state == "submitted" for assignment in self)
            )
            if manager_reason_only:
                return super().write(vals)
            self._check_current_user_is_tug_master()
            if any(assignment.completion_state not in {"pending", "returned"} for assignment in self):
                raise AccessError("A submitted completion record is locked. Return it for correction first.")
            forbidden = {"completion_state", "completion_declared_by_id", "completion_declared_at"}.intersection(vals)
            if forbidden:
                raise AccessError("Completion status and audit fields can only be changed by workflow actions.")
        result = super().write(vals)
        if "state" in vals:
            self.mapped("order_id").sync_completion_from_tugs()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        protected_values = {
            "actual_start", "actual_end", "completion_note", "completion_evidence",
            "completion_evidence_filename", "completion_declared_by_id",
            "completion_declared_at", "completion_return_reason",
        }
        invalid = any(
            any(vals.get(field_name) for field_name in protected_values)
            or vals.get("completion_state", "pending") != "pending"
            for vals in vals_list
        )
        if not self.env.su and invalid:
            raise AccessError("Completion fields must be maintained after assignment through the completion workflow.")
        return super().create(vals_list)

    def unlink(self):
        orders = self.mapped("order_id")
        result = super().unlink()
        orders.sync_completion_from_tugs()
        return result

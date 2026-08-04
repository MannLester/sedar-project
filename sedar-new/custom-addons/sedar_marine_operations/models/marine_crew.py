from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarTugboat(models.Model):
    _name = "sedar.tugboat"
    _description = "SEDAR Tugboat"
    _order = "name"

    name = fields.Char(required=True)
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

    order_id = fields.Many2one("sedar.marine.service.order", required=True, ondelete="cascade")
    tugboat_id = fields.Many2one("sedar.tugboat", required=True, ondelete="restrict")
    planned_start = fields.Datetime(related="order_id.requested_start", store=True)
    planned_end = fields.Datetime(related="order_id.requested_completion", store=True)
    state = fields.Selection([
        ("planned", "Planned"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")
    ], required=True, default="planned")
    tug_available = fields.Boolean(compute="_compute_tug_available", store=True)
    availability_reason = fields.Char(compute="_compute_tug_available", store=True)
    requirement_ids = fields.One2many("sedar.manning.requirement", "tug_assignment_id")

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


class SedarManningRequirement(models.Model):
    _name = "sedar.manning.requirement"
    _description = "Service Order Manning Requirement"
    _order = "rank_id"

    tug_assignment_id = fields.Many2one("sedar.tug.assignment", required=True, ondelete="cascade")
    rank_id = fields.Many2one("sedar.crew.rank", required=True, ondelete="restrict")
    required_count = fields.Integer(required=True, default=1)
    required_certificate_type_ids = fields.Many2many("sedar.crew.certificate.type")
    crew_assignment_ids = fields.One2many("sedar.crew.assignment", "requirement_id")
    assigned_count = fields.Integer(compute="_compute_coverage", store=True)
    gap_count = fields.Integer(compute="_compute_coverage", store=True)
    compliance_issue_count = fields.Integer(compute="_compute_coverage", store=True)
    status = fields.Selection([
        ("filled", "Filled"), ("shortage", "Shortage"), ("compliance", "Compliance Issue")
    ], compute="_compute_coverage", store=True)

    @api.depends("required_count", "crew_assignment_ids.state", "crew_assignment_ids.is_eligible")
    def _compute_coverage(self):
        for requirement in self:
            active_assignments = requirement.crew_assignment_ids.filtered(lambda line: line.state != "rejected")
            eligible = active_assignments.filtered("is_eligible")
            requirement.assigned_count = len(eligible)
            requirement.gap_count = max(requirement.required_count - len(eligible), 0)
            requirement.compliance_issue_count = len(active_assignments - eligible)
            if requirement.compliance_issue_count:
                requirement.status = "compliance"
            elif requirement.gap_count:
                requirement.status = "shortage"
            else:
                requirement.status = "filled"


class SedarCrewAssignment(models.Model):
    _name = "sedar.crew.assignment"
    _description = "Service Order Crew Assignment"
    _order = "requirement_id, crew_profile_id"

    requirement_id = fields.Many2one("sedar.manning.requirement", required=True, ondelete="cascade")
    tug_assignment_id = fields.Many2one(related="requirement_id.tug_assignment_id", store=True)
    order_id = fields.Many2one(related="tug_assignment_id.order_id", store=True)
    crew_profile_id = fields.Many2one("sedar.crew.profile", required=True, ondelete="restrict")
    employee_id = fields.Many2one(related="crew_profile_id.employee_id", store=True)
    rank_id = fields.Many2one(related="crew_profile_id.rank_id", store=True)
    state = fields.Selection([
        ("planned", "Planned"), ("confirmed", "Confirmed"), ("rejected", "Rejected")
    ], required=True, default="planned")
    is_eligible = fields.Boolean(compute="_compute_eligibility", store=True)
    eligibility_reason = fields.Char(compute="_compute_eligibility", store=True)

    @api.depends(
        "crew_profile_id.rank_id", "crew_profile_id.availability_status",
        "crew_profile_id.active", "crew_profile_id.certificate_ids.expiry_date",
        "requirement_id.required_certificate_type_ids", "order_id.requested_start",
        "order_id.requested_completion", "state"
    )
    def _compute_eligibility(self):
        for assignment in self:
            reasons = []
            profile = assignment.crew_profile_id
            requirement = assignment.requirement_id
            if not profile.active:
                reasons.append("Inactive crew profile")
            if profile.rank_id != requirement.rank_id:
                reasons.append("Incorrect rank")
            if profile.availability_status == "leave":
                reasons.append("Employee is on leave")
            elif profile.availability_status == "unavailable":
                reasons.append("Employee is unavailable")

            start_date = fields.Date.to_date(assignment.order_id.requested_start)
            valid_type_ids = profile.certificate_ids.filtered(
                lambda certificate: certificate.expiry_date >= start_date
            ).mapped("certificate_type_id").ids if start_date else []
            missing_types = requirement.required_certificate_type_ids.filtered(
                lambda cert_type: cert_type.id not in valid_type_ids
            )
            if missing_types:
                reasons.append("Missing/expired: %s" % ", ".join(missing_types.mapped("name")))

            if assignment.state != "rejected" and assignment.order_id.requested_start:
                overlapping = self.search_count([
                    ("id", "!=", assignment.id),
                    ("crew_profile_id", "=", profile.id),
                    ("state", "in", ["planned", "confirmed"]),
                    ("order_id.requested_start", "<", assignment.order_id.requested_completion),
                    ("order_id.requested_completion", ">", assignment.order_id.requested_start),
                ])
                if overlapping:
                    reasons.append("Overlapping crew assignment")
            assignment.is_eligible = not reasons
            assignment.eligibility_reason = "; ".join(reasons) or "Eligible"


class SedarCrewShortage(models.Model):
    _name = "sedar.crew.shortage"
    _description = "Service Order Crew Shortage"
    _order = "status, requirement_id"

    requirement_id = fields.Many2one("sedar.manning.requirement", required=True, ondelete="cascade")
    order_id = fields.Many2one(related="requirement_id.tug_assignment_id.order_id", store=True)
    tugboat_id = fields.Many2one(related="requirement_id.tug_assignment_id.tugboat_id", store=True)
    rank_id = fields.Many2one(related="requirement_id.rank_id", store=True)
    missing_count = fields.Integer(required=True, default=1)
    reason = fields.Selection([
        ("no_qualified", "No Qualified Employee"),
        ("already_assigned", "Already Assigned"),
        ("leave", "On Leave"),
        ("certificate", "Certificate or Medical Issue"),
        ("training", "Training Incomplete"),
    ], required=True)
    status = fields.Selection([
        ("open", "Open"), ("resolved", "Resolved"), ("cancelled", "Cancelled")
    ], required=True, default="open")
    notes = fields.Text()

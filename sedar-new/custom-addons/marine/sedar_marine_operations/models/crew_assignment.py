from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarManningRequirement(models.Model):
    _name = "sedar.manning.requirement"
    _description = "Service Order Manning Requirement"
    _order = "rank_id"
    _check_company_auto = True

    tug_assignment_id = fields.Many2one(
        "sedar.tug.assignment", required=True, ondelete="cascade", check_company=True,
    )
    company_id = fields.Many2one(related="tug_assignment_id.company_id", store=True, index=True)
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

    def write(self, vals):
        if "tug_assignment_id" in vals and any(
            requirement.tug_assignment_id.id != vals["tug_assignment_id"]
            for requirement in self
        ):
            raise ValidationError(
                "A manning requirement cannot move to another Tug Assignment."
            )
        return super().write(vals)


class SedarCrewAssignment(models.Model):
    _name = "sedar.crew.assignment"
    _description = "Service Order Crew Assignment"
    _order = "requirement_id, crew_profile_id"
    _check_company_auto = True

    requirement_id = fields.Many2one(
        "sedar.manning.requirement", required=True, ondelete="cascade", check_company=True,
    )
    tug_assignment_id = fields.Many2one(related="requirement_id.tug_assignment_id", store=True)
    order_id = fields.Many2one(related="tug_assignment_id.order_id", store=True)
    company_id = fields.Many2one(related="order_id.company_id", store=True, index=True)
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

    def write(self, vals):
        if "requirement_id" in vals and any(
            assignment.requirement_id.id != vals["requirement_id"]
            for assignment in self
        ):
            raise ValidationError(
                "A crew assignment cannot move to another Manning Requirement."
            )
        return super().write(vals)


class SedarCrewShortage(models.Model):
    _name = "sedar.crew.shortage"
    _description = "Service Order Crew Shortage"
    _order = "status, requirement_id"
    _check_company_auto = True

    requirement_id = fields.Many2one(
        "sedar.manning.requirement", required=True, ondelete="cascade", check_company=True,
    )
    order_id = fields.Many2one(related="requirement_id.tug_assignment_id.order_id", store=True)
    company_id = fields.Many2one(related="order_id.company_id", store=True, index=True)
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

    def write(self, vals):
        if "requirement_id" in vals and any(
            shortage.requirement_id.id != vals["requirement_id"]
            for shortage in self
        ):
            raise ValidationError(
                "A crew shortage cannot move to another Manning Requirement."
            )
        return super().write(vals)

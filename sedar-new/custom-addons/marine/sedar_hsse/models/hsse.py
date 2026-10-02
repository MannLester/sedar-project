from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .hsse_common import SEVERITIES, _check_hsse_manager


class SedarHsseSourceMixin(models.AbstractModel):
    _name = "sedar.hsse.source.mixin"
    _description = "SEDAR HSSE Source Links"

    service_order_id = fields.Many2one("sedar.marine.service.order", string="Service Order", ondelete="set null")
    operation_id = fields.Many2one("sedar.marine.operation", string="Marine Operation", ondelete="set null")
    tugboat_id = fields.Many2one("sedar.tugboat", ondelete="set null")
    berth_id = fields.Many2one("sedar.marine.berth", string="Terminal / Berth", ondelete="set null")
    maintenance_request_id = fields.Many2one("maintenance.request", string="Maintenance Work Order", ondelete="set null")
    document_request_id = fields.Many2one("sedar.document.request", string="Controlled Evidence", ondelete="set null")

    @api.onchange("operation_id")
    def _onchange_operation_id_hsse_source(self):
        if self.operation_id:
            self.service_order_id = self.operation_id.order_id

    @api.onchange("service_order_id")
    def _onchange_service_order_id_hsse_source(self):
        if self.service_order_id and not self.berth_id:
            self.berth_id = self.service_order_id.origin_berth_id


class SedarHsseIncident(models.Model):
    _name = "sedar.hsse.incident"
    _description = "HSSE Incident or Near Miss"
    _inherit = ["mail.thread", "mail.activity.mixin", "sedar.hsse.source.mixin"]
    _order = "occurrence_datetime desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    incident_type = fields.Selection(
        [("incident", "Incident"), ("near_miss", "Near Miss"), ("unsafe_condition", "Unsafe Condition")],
        required=True,
        default="incident",
        tracking=True,
    )
    category = fields.Selection(
        [
            ("people", "People"),
            ("vessel", "Vessel / Equipment"),
            ("environment", "Environment"),
            ("security", "Security"),
            ("operation", "Operation"),
            ("other", "Other"),
        ],
        required=True,
        default="operation",
        tracking=True,
    )
    severity = fields.Selection(SEVERITIES, required=True, default="medium", tracking=True)
    occurrence_datetime = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    reported_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    investigator_id = fields.Many2one("res.users")
    employee_ids = fields.Many2many("hr.employee", string="People Involved")
    crew_profile_ids = fields.Many2many("sedar.crew.profile", string="Crew Involved")
    summary = fields.Text(required=True)
    immediate_action = fields.Text()
    investigation_summary = fields.Text()
    root_cause = fields.Text()
    confidential = fields.Boolean(default=True)
    corrective_action_ids = fields.One2many("sedar.hsse.corrective.action", "incident_id")
    open_corrective_action_count = fields.Integer(compute="_compute_action_counts", store=True)
    state = fields.Selection(
        [
            ("reported", "Reported"),
            ("investigating", "Investigating"),
            ("action_required", "Action Required"),
            ("verified", "Verified Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="reported",
        required=True,
        tracking=True,
    )
    closed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    verified_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    verified_at = fields.Datetime(readonly=True, copy=False)

    @api.depends("corrective_action_ids.state")
    def _compute_action_counts(self):
        for incident in self:
            incident.open_corrective_action_count = len(
                incident.corrective_action_ids.filtered(lambda action: action.state not in {"verified", "cancelled"})
            )

    def action_start_investigation(self):
        _check_hsse_manager(self)
        self.write({
            "state": "investigating",
            "investigator_id": self.env.user.id,
        })
        return True

    def action_require_actions(self):
        _check_hsse_manager(self)
        for incident in self:
            if not incident.investigation_summary or not incident.root_cause:
                raise UserError("Investigation summary and root cause are required before assigning actions.")
            incident.state = "action_required"
        return True

    def action_verify_close(self):
        _check_hsse_manager(self)
        for incident in self:
            if not incident.investigation_summary or not incident.root_cause:
                raise UserError("Investigation summary and root cause are required before verified closure.")
            if incident.open_corrective_action_count:
                raise UserError("All corrective actions must be verified before closing the incident.")
            incident.write({
                "state": "verified",
                "closed_by_id": self.env.user.id,
                "closed_at": fields.Datetime.now(),
                "verified_by_id": self.env.user.id,
                "verified_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        _check_hsse_manager(self)
        self.write({"state": "cancelled"})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        incidents = super().create(vals_list)
        for incident in incidents:
            if incident.name == "New":
                incident.name = self.env["ir.sequence"].next_by_code("sedar.hsse.incident") or "New"
        return incidents


class SedarHsseInspection(models.Model):
    _name = "sedar.hsse.inspection"
    _description = "HSSE Inspection"
    _inherit = ["mail.thread", "mail.activity.mixin", "sedar.hsse.source.mixin"]
    _order = "inspection_datetime desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    inspection_type = fields.Selection(
        [
            ("vessel", "Vessel"),
            ("workplace", "Workplace"),
            ("permit", "Permit"),
            ("ppe", "PPE"),
            ("environment", "Environment"),
            ("other", "Other"),
        ],
        required=True,
        default="vessel",
        tracking=True,
    )
    inspection_datetime = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    inspector_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    summary = fields.Text(required=True)
    finding_ids = fields.One2many("sedar.hsse.inspection.finding", "inspection_id")
    finding_count = fields.Integer(compute="_compute_finding_counts", store=True)
    overdue_finding_count = fields.Integer(compute="_compute_finding_counts", store=True)
    state = fields.Selection(
        [("draft", "Draft"), ("completed", "Completed"), ("verified", "Verified"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        tracking=True,
    )

    @api.depends("finding_ids.state", "finding_ids.is_overdue")
    def _compute_finding_counts(self):
        for inspection in self:
            inspection.finding_count = len(inspection.finding_ids)
            inspection.overdue_finding_count = len(inspection.finding_ids.filtered("is_overdue"))

    def action_complete(self):
        _check_hsse_manager(self)
        self.write({"state": "completed"})
        return True

    def action_verify(self):
        _check_hsse_manager(self)
        for inspection in self:
            unresolved = inspection.finding_ids.filtered(lambda finding: finding.state not in {"closed", "cancelled"})
            if unresolved:
                raise UserError("Close or cancel all findings before verifying the inspection.")
            inspection.state = "verified"
        return True

    @api.model_create_multi
    def create(self, vals_list):
        inspections = super().create(vals_list)
        for inspection in inspections:
            if inspection.name == "New":
                inspection.name = self.env["ir.sequence"].next_by_code("sedar.hsse.inspection") or "New"
        return inspections


class SedarHsseInspectionFinding(models.Model):
    _name = "sedar.hsse.inspection.finding"
    _description = "HSSE Inspection Finding"
    _order = "due_date, severity desc, id"

    inspection_id = fields.Many2one("sedar.hsse.inspection", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    severity = fields.Selection(SEVERITIES, required=True, default="medium")
    assigned_user_id = fields.Many2one("res.users", required=True)
    due_date = fields.Date(required=True)
    description = fields.Text(required=True)
    corrective_action_id = fields.Many2one("sedar.hsse.corrective.action", readonly=True, copy=False)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", store=True)
    state = fields.Selection(
        [("open", "Open"), ("action_created", "Action Created"), ("closed", "Closed"), ("cancelled", "Cancelled")],
        default="open",
        required=True,
    )

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for finding in self:
            finding.is_overdue = bool(finding.due_date and finding.due_date < today and finding.state in {"open", "action_created"})

    def action_create_corrective_action(self):
        for finding in self:
            if finding.corrective_action_id:
                continue
            action = self.env["sedar.hsse.corrective.action"].create({
                "name": finding.name,
                "inspection_finding_id": finding.id,
                "assigned_user_id": finding.assigned_user_id.id,
                "due_date": finding.due_date,
                "severity": finding.severity,
                "critical_control": finding.severity == "critical",
                "description": finding.description,
            })
            finding.write({"corrective_action_id": action.id, "state": "action_created"})
        return True

    def action_close(self):
        _check_hsse_manager(self)
        self.write({"state": "closed"})
        return True


class SedarHsseRiskAssessment(models.Model):
    _name = "sedar.hsse.risk.assessment"
    _description = "HSSE Risk Assessment"
    _inherit = ["mail.thread", "mail.activity.mixin", "sedar.hsse.source.mixin"]
    _order = "assessment_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    assessment_date = fields.Date(default=fields.Date.context_today, required=True)
    hazard = fields.Char(required=True)
    activity = fields.Char(required=True)
    existing_controls = fields.Text(required=True)
    additional_controls = fields.Text()
    likelihood = fields.Integer(required=True, default=1)
    impact = fields.Integer(required=True, default=1)
    residual_risk_score = fields.Integer(compute="_compute_residual_risk_score", store=True)
    residual_risk_level = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        compute="_compute_residual_risk_score",
        store=True,
    )
    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    corrective_action_ids = fields.One2many("sedar.hsse.corrective.action", "risk_assessment_id")
    state = fields.Selection([("draft", "Draft"), ("approved", "Approved"), ("retired", "Retired")], default="draft", required=True)

    @api.depends("likelihood", "impact")
    def _compute_residual_risk_score(self):
        for assessment in self:
            score = assessment.likelihood * assessment.impact
            assessment.residual_risk_score = score
            if score >= 16:
                assessment.residual_risk_level = "critical"
            elif score >= 10:
                assessment.residual_risk_level = "high"
            elif score >= 4:
                assessment.residual_risk_level = "medium"
            else:
                assessment.residual_risk_level = "low"

    @api.constrains("likelihood", "impact")
    def _check_risk_matrix_values(self):
        for assessment in self:
            if not 1 <= assessment.likelihood <= 5 or not 1 <= assessment.impact <= 5:
                raise ValidationError("Likelihood and impact must be between 1 and 5.")

    def action_approve(self):
        _check_hsse_manager(self)
        self.write({
            "state": "approved",
            "approved_by_id": self.env.user.id,
            "approved_at": fields.Datetime.now(),
        })
        return True

    @api.model_create_multi
    def create(self, vals_list):
        assessments = super().create(vals_list)
        for assessment in assessments:
            if assessment.name == "New":
                assessment.name = self.env["ir.sequence"].next_by_code("sedar.hsse.risk.assessment") or "New"
        return assessments


class SedarHssePermit(models.Model):
    _name = "sedar.hsse.permit"
    _description = "HSSE Permit Register"
    _inherit = ["mail.thread", "mail.activity.mixin", "sedar.hsse.source.mixin"]
    _order = "valid_until, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    permit_type = fields.Selection(
        [
            ("hot_work", "Hot Work"),
            ("confined_space", "Confined Space"),
            ("environmental", "Environmental"),
            ("port_authority", "Port Authority"),
            ("security", "Security"),
            ("other", "Other"),
        ],
        required=True,
        default="port_authority",
        tracking=True,
    )
    permit_number = fields.Char(required=True)
    issuing_authority = fields.Char()
    valid_from = fields.Date(required=True)
    valid_until = fields.Date(required=True)
    required_for_operations = fields.Boolean(default=True)
    is_expired = fields.Boolean(compute="_compute_permit_status", store=True)
    operational_exception = fields.Boolean(compute="_compute_permit_status", store=True)
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")],
        compute="_compute_permit_status",
        store=True,
        default="draft",
        required=True,
    )
    note = fields.Text()

    @api.depends("valid_until", "required_for_operations")
    def _compute_permit_status(self):
        today = fields.Date.context_today(self)
        for permit in self:
            permit.is_expired = bool(permit.valid_until and permit.valid_until < today)
            permit.operational_exception = permit.required_for_operations and permit.is_expired
            if permit.state != "cancelled":
                permit.state = "expired" if permit.is_expired else "active"

    @api.constrains("valid_from", "valid_until")
    def _check_validity_dates(self):
        for permit in self:
            if permit.valid_until < permit.valid_from:
                raise ValidationError("Permit valid-until date cannot be earlier than valid-from date.")

    @api.model_create_multi
    def create(self, vals_list):
        permits = super().create(vals_list)
        for permit in permits:
            if permit.name == "New":
                permit.name = self.env["ir.sequence"].next_by_code("sedar.hsse.permit") or "New"
        permits._compute_permit_status()
        return permits

    def write(self, vals):
        result = super().write(vals)
        if {"valid_from", "valid_until", "required_for_operations"}.intersection(vals):
            self._compute_permit_status()
        return result

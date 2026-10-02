from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarCrewOnboarding(models.Model):
    _name = "sedar.crew.onboarding"
    _description = "SEDAR Marine Crew Onboarding"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", index=True)
    applicant_id = fields.Many2one("hr.applicant", related="employee_id.sedar_source_applicant_id", store=True, readonly=True)
    vacancy_id = fields.Many2one("sedar.job.vacancy", related="employee_id.sedar_source_vacancy_id", store=True, readonly=True)
    manpower_request_line_id = fields.Many2one(
        "sedar.manpower.request.line",
        related="vacancy_id.request_line_id",
        store=True,
        readonly=True,
    )
    rank_id = fields.Many2one("sedar.crew.rank", required=True, ondelete="restrict", tracking=True)
    home_tugboat_id = fields.Many2one("sedar.tugboat", string="Home Tugboat", tracking=True)
    crew_profile_id = fields.Many2one("sedar.crew.profile", readonly=True, copy=False, ondelete="set null")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("blocked", "Blocked"),
            ("deployment_eligible", "Deployment Eligible"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    required_certificate_type_ids = fields.Many2many(
        "sedar.crew.certificate.type",
        "sedar_crew_onboarding_required_cert_rel",
        "onboarding_id",
        "certificate_type_id",
        string="Required Credentials / Medicals",
    )
    missing_certificate_type_ids = fields.Many2many(
        "sedar.crew.certificate.type",
        compute="_compute_deployment_status",
        compute_sudo=True,
        store=True,
        string="Missing Credentials / Medicals",
    )
    deployment_eligible = fields.Boolean(compute="_compute_deployment_status", compute_sudo=True, store=True)
    blocker_summary = fields.Char(compute="_compute_deployment_status", compute_sudo=True, store=True)
    opened_by_id = fields.Many2one("res.users", readonly=True, copy=False, default=lambda self: self.env.user)
    opened_at = fields.Datetime(readonly=True, copy=False, default=fields.Datetime.now)
    verified_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    verified_at = fields.Datetime(readonly=True, copy=False)
    notes = fields.Text()

    _employee_unique = models.Constraint(
        "UNIQUE(employee_id)",
        "An employee can have only one marine crew onboarding case.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == "New":
                record.name = self.env["ir.sequence"].next_by_code("sedar.crew.onboarding") or "New"
        return records

    @api.constrains("employee_id", "rank_id")
    def _check_employee_rank(self):
        for onboarding in self:
            if onboarding.vacancy_id and onboarding.vacancy_id.crew_rank_id != onboarding.rank_id:
                raise ValidationError("The onboarding rank must match the source marine vacancy rank.")

    @api.depends(
        "crew_profile_id",
        "crew_profile_id.active",
        "crew_profile_id.rank_id",
        "crew_profile_id.home_tugboat_id",
        "crew_profile_id.certificate_ids.certificate_type_id",
        "crew_profile_id.certificate_ids.expiry_date",
        "rank_id",
        "home_tugboat_id",
        "required_certificate_type_ids",
    )
    def _compute_deployment_status(self):
        today = fields.Date.context_today(self)
        for onboarding in self:
            reasons = []
            missing = self.env["sedar.crew.certificate.type"]
            profile = onboarding.crew_profile_id
            if not profile:
                reasons.append("Crew Profile not created")
            else:
                if not profile.active:
                    reasons.append("Crew Profile inactive")
                if profile.rank_id != onboarding.rank_id:
                    reasons.append("Crew Profile rank mismatch")
                if not profile.home_tugboat_id:
                    reasons.append("Home tugboat missing")
                valid_types = profile.certificate_ids.filtered(
                    lambda certificate: certificate.expiry_date >= today
                ).mapped("certificate_type_id")
                missing = onboarding.required_certificate_type_ids - valid_types
                if missing:
                    reasons.append("Missing/expired: %s" % ", ".join(missing.mapped("name")))
            onboarding.missing_certificate_type_ids = missing
            onboarding.deployment_eligible = not reasons
            onboarding.blocker_summary = "; ".join(reasons) or "Deployment eligible"

    @api.model
    def _sedar_get_or_create_from_employee(self, employee):
        employee = employee.sudo().exists()
        if not employee:
            return self.browse()
        existing = self.sudo().search([("employee_id", "=", employee.id)], limit=1)
        if existing:
            return existing
        vacancy = employee.sedar_source_vacancy_id
        if not vacancy or not vacancy.crew_rank_id:
            return self.browse()
        return self.sudo().create({
            "employee_id": employee.id,
            "rank_id": vacancy.crew_rank_id.id,
            "home_tugboat_id": False,
            "required_certificate_type_ids": [
                fields.Command.set(self._sedar_required_certificate_types(vacancy).ids)
            ],
            "state": "draft",
            "notes": "Generated from applicant-to-employee conversion. Crewing must complete marine readiness before deployment.",
        })

    def _sedar_required_certificate_types(self, vacancy):
        certificate_types = vacancy.request_line_id.required_certificate_type_ids
        if certificate_types:
            return certificate_types
        template_lines = self.env["sedar.manning.template.line"].search([
            ("rank_id", "=", vacancy.crew_rank_id.id),
            ("template_id.active", "=", True),
        ])
        return template_lines.mapped("required_certificate_type_ids")

    def action_start(self):
        self._ensure_crewing_manager()
        for onboarding in self:
            if onboarding.state not in ("draft", "blocked"):
                raise UserError("Only draft or blocked onboarding cases can be started.")
            onboarding.write({"state": "in_progress"})
        return True

    def action_create_crew_profile(self):
        self._ensure_crewing_manager()
        for onboarding in self:
            profile = onboarding.crew_profile_id or self.env["sedar.crew.profile"].sudo().search([
                ("employee_id", "=", onboarding.employee_id.id),
            ], limit=1)
            if not profile:
                profile = self.env["sedar.crew.profile"].sudo().create({
                    "employee_id": onboarding.employee_id.id,
                    "employee_number": self.env["ir.sequence"].next_by_code("sedar.crew.profile") or "SEDAR-CREW-NEW",
                    "rank_id": onboarding.rank_id.id,
                    "home_tugboat_id": onboarding.home_tugboat_id.id,
                    "seafarer_number": "PENDING-%s" % onboarding.employee_id.id,
                    "availability_status": "unavailable",
                })
            else:
                profile.sudo().write({
                    "rank_id": onboarding.rank_id.id,
                    "home_tugboat_id": onboarding.home_tugboat_id.id or profile.home_tugboat_id.id,
                    "availability_status": "unavailable" if profile.availability_status == "available" else profile.availability_status,
                })
            onboarding.write({
                "crew_profile_id": profile.id,
                "state": "in_progress",
            })
        return True

    def action_mark_deployment_eligible(self):
        self._ensure_crewing_manager()
        for onboarding in self:
            onboarding.flush_recordset()
            if not onboarding.deployment_eligible:
                onboarding.write({"state": "blocked"})
                continue
            onboarding.crew_profile_id.sudo().write({
                "availability_status": "available",
                "home_tugboat_id": onboarding.home_tugboat_id.id or onboarding.crew_profile_id.home_tugboat_id.id,
            })
            onboarding.write({
                "state": "deployment_eligible",
                "verified_by_id": self.env.user.id,
                "verified_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        self._ensure_crewing_manager()
        self.write({"state": "cancelled"})
        return True

    def _ensure_crewing_manager(self):
        if not self.env.user.has_group("sedar_recruitment_crewing.group_crewing_manager"):
            raise UserError("Only a Crewing Manager may control marine crew onboarding.")
        return True

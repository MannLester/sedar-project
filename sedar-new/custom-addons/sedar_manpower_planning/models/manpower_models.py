from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


ROOT_CAUSES = [
    ("scheduling", "Scheduling Conflict"),
    ("leave", "Employee on Leave"),
    ("unavailable", "Employee Unavailable"),
    ("certificate", "Missing or Expired Certificate"),
    ("medical", "Medical Issue"),
    ("training", "Training Incomplete"),
    ("no_qualified", "No Qualified Employee"),
    ("permanent_headcount", "Permanent Headcount Shortage"),
    ("temporary_headcount", "Temporary Headcount Shortage"),
    ("data_correction", "Data Correction Required"),
    ("other", "Other"),
]


class SedarCrewShortage(models.Model):
    _inherit = "sedar.crew.shortage"

    detected_at = fields.Datetime(default=fields.Datetime.now, required=True)
    crew_assignment_id = fields.Many2one(
        "sedar.crew.assignment", ondelete="set null", check_company=True
    )
    operation_id = fields.Many2one(
        "sedar.marine.operation", compute="_compute_operation", store=True, check_company=True
    )
    review_state = fields.Selection([
        ("unreviewed", "Unreviewed"), ("reviewing", "Under Review"),
        ("action_required", "Action Required"), ("escalated", "Escalated"),
        ("resolved", "Resolved"),
    ], default="unreviewed", required=True)
    root_cause = fields.Selection(ROOT_CAUSES)
    reviewer_id = fields.Many2one("res.users")
    reviewed_at = fields.Datetime()
    resolution_action = fields.Selection([
        ("replacement", "Assign Replacement"), ("reschedule", "Reschedule Service"),
        ("certificate", "Renew Certificate"), ("medical", "Schedule Medical"),
        ("training", "Schedule Training"), ("temporary_reliever", "Request Temporary Reliever"),
        ("manpower_request", "Submit Manpower Request"), ("close", "Close Without Action"),
    ])
    resolution_notes = fields.Text()
    resolved_at = fields.Datetime()
    action_ids = fields.One2many("sedar.crew.shortage.action", "shortage_id")
    manpower_request_line_id = fields.Many2one(
        "sedar.manpower.request.line", ondelete="set null", check_company=True
    )

    @api.depends("order_id.operation_ids")
    def _compute_operation(self):
        for shortage in self:
            shortage.operation_id = shortage.order_id.operation_ids[:1]

    @api.constrains(
        "company_id", "crew_assignment_id", "operation_id", "manpower_request_line_id"
    )
    def _check_company_links(self):
        for shortage in self:
            linked_records = (
                shortage.crew_assignment_id,
                shortage.operation_id,
                shortage.manpower_request_line_id,
            )
            if any(
                linked.company_id and linked.company_id != shortage.company_id
                for linked in linked_records
            ):
                raise ValidationError(
                    "Crew shortage links must belong to the Service Order company."
                )

    def action_start_review(self):
        self.write({"review_state": "reviewing", "reviewer_id": self.env.user.id})
        return True

    def action_mark_action_required(self):
        for shortage in self:
            if not shortage.root_cause or not shortage.resolution_action:
                raise UserError("Select a root cause and resolution action before continuing.")
            shortage.write({
                "review_state": "action_required", "reviewer_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            })
        return True

    def action_escalate(self):
        for shortage in self:
            if shortage.root_cause not in {"permanent_headcount", "temporary_headcount"}:
                raise UserError("Only headcount-related shortages can be escalated to manpower planning.")
            shortage.write({
                "review_state": "escalated", "reviewer_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            })
        return True

    def action_resolve(self):
        for shortage in self:
            shortage.write({
                "review_state": "resolved", "status": "resolved",
                "resolved_at": fields.Datetime.now(),
            })
        return True

    def action_create_manpower_request(self):
        self.ensure_one()
        if self.review_state != "escalated":
            raise UserError("Escalate the shortage as a headcount issue before creating a request.")
        if self.manpower_request_line_id:
            return self.manpower_request_line_id.request_id.action_open()
        company = self.company_id
        department = self.env["hr.department"].search([
            ("name", "ilike", "marine"),
            ("company_id", "in", [False, company.id]),
        ], order="company_id desc, id", limit=1)
        request = self.env["sedar.manpower.request"].with_company(company).create({
            "company_id": company.id,
            "department_id": department.id,
            "requested_by": self.env.user.id,
            "business_justification": "Operational crew shortage linked to service order %s." % self.order_id.name,
            "operational_impact": self.notes or self.readiness_context,
        })
        line = self.env["sedar.manpower.request.line"].create({
            "request_id": request.id,
            "crew_rank_id": self.rank_id.id,
            "quantity": self.missing_count,
            "approved_quantity": self.missing_count,
            "required_date": fields.Date.to_date(self.order_id.requested_start),
            "shortage_ids": [fields.Command.link(self.id)],
            "request_type": "permanent" if self.root_cause == "permanent_headcount" else "temporary",
        })
        self.manpower_request_line_id = line.id
        return request.action_open()

    @property
    def readiness_context(self):
        self.ensure_one()
        return "Crew rank: %s; Tugboat: %s; Missing count: %s" % (
            self.rank_id.name, self.tugboat_id.name, self.missing_count,
        )


class SedarCrewShortageAction(models.Model):
    _name = "sedar.crew.shortage.action"
    _description = "Crew Shortage Resolution Action"
    _order = "planned_date desc, id desc"
    _check_company_auto = True

    shortage_id = fields.Many2one(
        "sedar.crew.shortage", required=True, ondelete="cascade", check_company=True
    )
    company_id = fields.Many2one(
        related="shortage_id.company_id", store=True, index=True, readonly=True
    )
    action_type = fields.Selection([
        ("replacement", "Replacement"), ("reschedule", "Reschedule"),
        ("certificate", "Certification"), ("medical", "Medical"),
        ("training", "Training"), ("manpower", "Manpower Request"),
    ], required=True)
    assigned_employee_id = fields.Many2one("hr.employee", check_company=True)

    @api.constrains("company_id", "assigned_employee_id")
    def _check_assigned_employee_company(self):
        for action in self:
            employee = action.assigned_employee_id
            if employee.company_id and employee.company_id != action.company_id:
                raise ValidationError(
                    "The assigned employee must belong to the shortage action company."
                )
    responsible_user_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    planned_date = fields.Date()
    completed_date = fields.Date()
    state = fields.Selection([
        ("planned", "Planned"), ("in_progress", "In Progress"),
        ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled"),
    ], default="planned", required=True)
    outcome = fields.Text()
    attachment_ids = fields.Many2many("ir.attachment", string="Evidence")

    def write(self, vals):
        if "shortage_id" in vals and any(
            action.shortage_id.id != vals["shortage_id"] for action in self
        ):
            raise ValidationError(
                "A shortage resolution action cannot move to another Crew Shortage."
            )
        return super().write(vals)

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_complete(self):
        for action in self:
            if not action.outcome:
                raise UserError("Enter the action outcome before completing it.")
            action.write({"state": "completed", "completed_date": fields.Date.context_today(self)})
            if action.action_type != "manpower":
                action.shortage_id.action_resolve()

    def action_fail(self):
        self.write({"state": "failed"})


class SedarManpowerRequest(models.Model):
    _name = "sedar.manpower.request"
    _description = "SEDAR Manpower Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one("hr.department", required=True, check_company=True)
    requested_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    request_date = fields.Date(default=fields.Date.context_today, required=True)
    priority = fields.Selection([
        ("normal", "Normal"), ("urgent", "Urgent"), ("critical", "Critical"),
    ], default="normal", required=True)
    business_justification = fields.Text(required=True)
    operational_impact = fields.Text()
    hr_reviewer_id = fields.Many2one("res.users")
    operations_approver_id = fields.Many2one("res.users")
    submitted_at = fields.Datetime()
    approved_at = fields.Datetime()
    rejection_reason = fields.Text()
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("hr_review", "HR Review"),
        ("manager_approval", "Management Approval"), ("approved", "Approved"),
        ("position_open", "Position Open"), ("rejected", "Rejected"),
        ("cancelled", "Cancelled"), ("closed", "Closed"),
    ], default="draft", required=True, tracking=True)
    line_ids = fields.One2many("sedar.manpower.request.line", "request_id")
    vacancy_count = fields.Integer(compute="_compute_counts")
    shortage_count = fields.Integer(compute="_compute_counts")
    attachment_ids = fields.Many2many("ir.attachment", string="Supporting Documents")

    @api.depends("line_ids.vacancy_id", "line_ids.shortage_ids")
    def _compute_counts(self):
        for request in self:
            request.vacancy_count = len(request.line_ids.mapped("vacancy_id"))
            request.shortage_count = len(request.line_ids.mapped("shortage_ids"))

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for request in requests:
            if request.name == "New":
                request.name = self.env["ir.sequence"].next_by_code("sedar.manpower.request") or "New"
        return requests

    def write(self, vals):
        if "company_id" in vals:
            changed_with_lines = self.filtered(
                lambda request: request.company_id.id != vals["company_id"]
                and request.line_ids
            )
            if changed_with_lines:
                raise ValidationError(
                    "A Manpower Request company cannot change after position lines exist."
                )
        return super().write(vals)

    def _ensure_group(self, xmlid):
        if not self.env.user.has_group(xmlid):
            raise UserError("You do not have permission to perform this approval action.")

    def _schedule_role_activity(self, group_xmlid, summary, note):
        users = self.env.ref(group_xmlid).users.filtered(lambda user: user.active)
        if users:
            self.activity_schedule(
                "mail.mail_activity_data_todo", user_id=users[0].id,
                summary=summary, note=note,
            )

    def action_open(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Manpower Request", "res_model": self._name, "res_id": self.id, "view_mode": "form"}

    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError("Add at least one requested position.")
            if not request.business_justification:
                raise UserError("Enter the business justification.")
            if any(not line.job_id for line in request.line_ids):
                raise UserError("Each request line must have an HR job position before submission.")
            request.write({"state": "submitted", "submitted_at": fields.Datetime.now()})
            request._schedule_role_activity(
                "sedar_manpower_planning.group_hr_reviewer",
                "Review manpower request", "Review the submitted manpower request and its operational evidence.",
            )
        return True

    def action_start_hr_review(self):
        self._ensure_group("sedar_manpower_planning.group_hr_reviewer")
        self.write({"state": "hr_review", "hr_reviewer_id": self.env.user.id})
        return True

    def action_submit_for_approval(self):
        self._ensure_group("sedar_manpower_planning.group_hr_reviewer")
        for request in self:
            if request.state != "hr_review":
                raise UserError("Only requests under HR review can be submitted for approval.")
            if any(line.quantity < 1 or not line.required_date for line in request.line_ids):
                raise UserError("Each request line needs a positive quantity and required date.")
            request.write({"state": "manager_approval"})
            request._schedule_role_activity(
                "sedar_manpower_planning.group_manpower_approver",
                "Approve manpower request", "Review the requested headcount and approve or reject it.",
            )
        return True

    def action_approve(self):
        self._ensure_group("sedar_manpower_planning.group_manpower_approver")
        for request in self:
            if request.state != "manager_approval":
                raise UserError("Only requests awaiting management approval can be approved.")
            if any(line.approved_quantity < 1 or line.approved_quantity > line.quantity for line in request.line_ids):
                raise UserError("Approved quantity must be between one and the requested quantity.")
            request.write({"state": "approved", "approved_at": fields.Datetime.now(), "operations_approver_id": self.env.user.id})
            request._schedule_role_activity(
                "sedar_manpower_planning.group_hr_manager",
                "Open approved position", "Create the internal vacancy record from this approved manpower request.",
            )
        return True

    def action_open_vacancies(self):
        self._ensure_group("sedar_manpower_planning.group_hr_manager")
        for request in self:
            if request.state != "approved":
                raise UserError("Only approved requests can open positions.")
            for line in request.line_ids:
                vacancy = line.vacancy_id or self.env["sedar.job.vacancy"].create({
                    "request_line_id": line.id,
                    "job_id": line.job_id.id,
                    "crew_rank_id": line.crew_rank_id.id,
                    "department_id": request.department_id.id,
                    "employment_type": line.request_type,
                    "approved_openings": line.approved_quantity,
                    "opening_date": fields.Date.context_today(self),
                    "application_deadline": line.required_date,
                    "website_title": line.job_id.name,
                    "website_summary": "SEDAR marine crew position. Publication requires HR approval.",
                    "requirements": line.required_qualifications,
                    "publication_state": "internal",
                })
                line.vacancy_id = vacancy.id
            request.write({"state": "position_open"})
        return True

    def _sedar_sync_headcount_fulfillment(self):
        for request in self:
            if request.state not in ("position_open", "approved"):
                continue
            vacancies = request.line_ids.mapped("vacancy_id")
            if vacancies and all(not vacancy.remaining_openings for vacancy in vacancies):
                request.write({"state": "closed"})

    def action_reject(self):
        self._ensure_group("sedar_manpower_planning.group_hr_reviewer")
        for request in self:
            if not request.rejection_reason:
                raise UserError("Enter a rejection reason first.")
            request.write({"state": "rejected"})

    def action_cancel(self):
        self.write({"state": "cancelled"})


class SedarManpowerRequestLine(models.Model):
    _name = "sedar.manpower.request.line"
    _description = "Manpower Request Position"
    _check_company_auto = True

    request_id = fields.Many2one(
        "sedar.manpower.request", required=True, ondelete="cascade", check_company=True
    )
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, index=True, readonly=True
    )
    crew_rank_id = fields.Many2one("sedar.crew.rank", required=True, ondelete="restrict")
    job_id = fields.Many2one("hr.job", ondelete="restrict", check_company=True)
    request_type = fields.Selection([
        ("permanent", "Permanent"), ("fixed_term", "Fixed-Term"),
        ("temporary", "Temporary Reliever"),
    ], required=True, default="permanent")
    quantity = fields.Integer(required=True, default=1)
    approved_quantity = fields.Integer(default=1)
    required_date = fields.Date(required=True)
    shortage_ids = fields.Many2many(
        "sedar.crew.shortage", string="Operational Evidence", check_company=True
    )
    required_certificate_type_ids = fields.Many2many("sedar.crew.certificate.type")
    minimum_experience_years = fields.Float()
    required_qualifications = fields.Text()
    vacancy_id = fields.Many2one("sedar.job.vacancy", readonly=True, ondelete="set null")

    @api.constrains("quantity", "approved_quantity")
    def _check_quantities(self):
        for line in self:
            if line.quantity < 1:
                raise ValidationError("Requested quantity must be at least one.")
            if line.approved_quantity < 0 or line.approved_quantity > line.quantity:
                raise ValidationError("Approved quantity must be between zero and requested quantity.")

    def write(self, vals):
        if "request_id" in vals and any(
            line.request_id.id != vals["request_id"] for line in self
        ):
            raise ValidationError(
                "A Manpower Request line cannot move to another Manpower Request."
            )
        return super().write(vals)

    @api.constrains("request_id", "shortage_ids")
    def _check_shortage_companies(self):
        for line in self:
            foreign_shortages = line.shortage_ids.filtered(
                lambda shortage: shortage.company_id != line.company_id
            )
            if foreign_shortages:
                raise ValidationError(
                    "Operational crew shortages must belong to the Manpower Request company."
                )

    @api.constrains("company_id", "job_id")
    def _check_job_company(self):
        for line in self:
            if line.job_id.company_id and line.job_id.company_id != line.company_id:
                raise ValidationError(
                    "The requested HR job must belong to the Manpower Request company."
                )


class SedarJobVacancy(models.Model):
    _name = "sedar.job.vacancy"
    _description = "SEDAR Job Vacancy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "opening_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    request_line_id = fields.Many2one("sedar.manpower.request.line", required=True, ondelete="restrict")
    job_id = fields.Many2one("hr.job", required=True, ondelete="restrict")
    crew_rank_id = fields.Many2one("sedar.crew.rank", ondelete="restrict")
    department_id = fields.Many2one("hr.department", required=True, ondelete="restrict")
    employment_type = fields.Selection([
        ("permanent", "Permanent"), ("fixed_term", "Fixed-Term"),
        ("temporary", "Temporary Reliever"),
    ], required=True)
    approved_openings = fields.Integer(required=True, default=1)
    filled_openings = fields.Integer(default=0)
    remaining_openings = fields.Integer(compute="_compute_remaining", store=True)
    opening_date = fields.Date(required=True)
    application_deadline = fields.Date()
    website_title = fields.Char(required=True)
    website_summary = fields.Text()
    responsibilities = fields.Text()
    requirements = fields.Text()
    publication_state = fields.Selection([
        ("internal", "Internal Only"), ("approved", "Approved for Publication"),
        ("published", "Published"), ("closed", "Closed"),
    ], default="internal", required=True, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("open", "Open"), ("on_hold", "On Hold"),
        ("filled", "Filled"), ("closed", "Closed"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, tracking=True)
    active = fields.Boolean(default=True)

    @api.depends("approved_openings", "filled_openings")
    def _compute_remaining(self):
        for vacancy in self:
            vacancy.remaining_openings = max(vacancy.approved_openings - vacancy.filled_openings, 0)

    @api.model_create_multi
    def create(self, vals_list):
        vacancies = super().create(vals_list)
        for vacancy in vacancies:
            if vacancy.name == "New":
                vacancy.name = self.env["ir.sequence"].next_by_code("sedar.job.vacancy") or "New"
        return vacancies

    def action_open(self):
        self.write({"state": "open"})

    def action_approve_publication(self):
        if not self.env.user.has_group("sedar_manpower_planning.group_hr_manager"):
            raise UserError("Only an HR Manager can approve a vacancy for publication.")
        self.write({"publication_state": "approved"})

    def action_close(self):
        self.write({"state": "closed", "publication_state": "closed"})

    def _sedar_sync_hiring_fulfillment(self):
        employee_model = self.env["hr.employee"].sudo()
        for vacancy in self:
            hired_count = employee_model.search_count([("sedar_source_vacancy_id", "=", vacancy.id)])
            filled = min(hired_count, vacancy.approved_openings)
            values = {"filled_openings": filled}
            if filled >= vacancy.approved_openings and vacancy.state not in ("closed", "cancelled"):
                values["state"] = "filled"
                values["publication_state"] = "closed"
            elif vacancy.state == "filled" and filled < vacancy.approved_openings:
                values["state"] = "open"
                if vacancy.publication_state == "closed":
                    values["publication_state"] = "approved"
            vacancy.write(values)
            vacancy.request_line_id.request_id._sedar_sync_headcount_fulfillment()


class SedarMarineServiceOrder(models.Model):
    _inherit = "sedar.marine.service.order"

    shortage_count = fields.Integer(compute="_compute_manpower_summary")
    manpower_request_count = fields.Integer(compute="_compute_manpower_summary")

    @api.depends("tug_assignment_ids.requirement_ids")
    def _compute_manpower_summary(self):
        shortage_model = self.env["sedar.crew.shortage"]
        for order in self:
            shortages = shortage_model.search([("order_id", "=", order.id)])
            order.shortage_count = len(shortages.filtered(lambda shortage: shortage.status == "open"))
            order.manpower_request_count = len(shortages.mapped("manpower_request_line_id.request_id"))

    def action_open_shortages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Crew Shortages",
            "res_model": "sedar.crew.shortage",
            "view_mode": "list,form",
            "domain": [("order_id", "=", self.id)],
        }

    def action_open_manpower_requests(self):
        self.ensure_one()
        request_ids = self.env["sedar.crew.shortage"].search([
            ("order_id", "=", self.id)
        ]).mapped("manpower_request_line_id.request_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": "Manpower Requests",
            "res_model": "sedar.manpower.request",
            "view_mode": "list,form",
            "domain": [("id", "in", request_ids)],
        }

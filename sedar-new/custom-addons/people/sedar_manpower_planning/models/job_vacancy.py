from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    @api.private
    def sedar_sync_hiring_fulfillment(self):
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

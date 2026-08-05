from datetime import datetime

from odoo import Command, api, fields, models


MODULE = "sedar_erp_demo"


def _record(env, model_name, xmlid, values):
    data = env["ir.model.data"].search([("module", "=", MODULE), ("name", "=", xmlid)], limit=1)
    if data:
        record = env[model_name].browse(data.res_id).exists()
        if record:
            return record
        data.unlink()
    record = env[model_name].create(values)
    env["ir.model.data"].create({"module": MODULE, "name": xmlid, "model": model_name, "res_id": record.id, "noupdate": True})
    return record


class SedarHrPerformanceReview(models.Model):
    _name = "sedar.hr.performance.review"
    _description = "SEDAR Demonstration Performance Review"
    _order = "review_date desc, id desc"

    name = fields.Char(required=True, default="Performance Review")
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict")
    reviewer_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="restrict")
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    review_date = fields.Date(required=True, default=fields.Date.context_today)
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved")], default="draft", required=True)
    rating = fields.Selection([("needs_improvement", "Needs Improvement"), ("meets", "Meets Expectations"), ("exceeds", "Exceeds Expectations")], required=True)
    strengths = fields.Text()
    development_goals = fields.Text()
    manager_summary = fields.Text()
    demonstration_only = fields.Boolean(default=True, readonly=True)


class SedarHrPayrollInput(models.Model):
    _name = "sedar.hr.payroll.input"
    _description = "SEDAR Demonstration Payroll Input Facts"
    _order = "period_end desc, employee_id"

    name = fields.Char(required=True, default="Payroll Input Facts")
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict")
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    attendance_hours = fields.Float()
    approved_leave_hours = fields.Float()
    eligible_crew_days = fields.Float()
    source_note = fields.Text(required=True)
    demonstration_only = fields.Boolean(default=True, readonly=True)


class SedarFinanceBudget(models.Model):
    _name = "sedar.finance.budget"
    _description = "SEDAR Demonstration Budget"

    name = fields.Char(required=True)
    department_id = fields.Many2one("hr.department", ondelete="restrict")
    tugboat_id = fields.Many2one("sedar.tugboat", ondelete="restrict")
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    planned_amount = fields.Monetary(required=True)
    actual_amount = fields.Monetary(required=True)
    variance = fields.Monetary(compute="_compute_variance", currency_field="currency_id")
    note = fields.Text()
    demonstration_only = fields.Boolean(default=True, readonly=True)

    @api.depends("planned_amount", "actual_amount")
    def _compute_variance(self):
        for record in self:
            record.variance = record.planned_amount - record.actual_amount


class SedarFixedAsset(models.Model):
    _name = "sedar.fixed.asset"
    _description = "SEDAR Demonstration Fixed Asset"

    name = fields.Char(required=True)
    tugboat_id = fields.Many2one("sedar.tugboat", ondelete="restrict")
    equipment_id = fields.Many2one("maintenance.equipment", ondelete="restrict")
    acquisition_date = fields.Date(required=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    original_value = fields.Monetary(required=True)
    residual_value = fields.Monetary(default=0)
    useful_life_months = fields.Integer(required=True, default=120)
    monthly_depreciation = fields.Monetary(compute="_compute_depreciation", currency_field="currency_id")
    accumulated_depreciation = fields.Monetary(compute="_compute_depreciation", currency_field="currency_id")
    demonstration_only = fields.Boolean(default=True, readonly=True)

    @api.depends("acquisition_date", "original_value", "residual_value", "useful_life_months")
    def _compute_depreciation(self):
        today = fields.Date.context_today(self)
        for record in self:
            depreciable = max(record.original_value - record.residual_value, 0)
            record.monthly_depreciation = depreciable / record.useful_life_months if record.useful_life_months else 0
            if record.acquisition_date and record.monthly_depreciation:
                months = max((today.year - record.acquisition_date.year) * 12 + today.month - record.acquisition_date.month, 0)
                record.accumulated_depreciation = min(depreciable, months * record.monthly_depreciation)
            else:
                record.accumulated_depreciation = 0


class CrmLead(models.Model):
    _inherit = "crm.lead"

    sedar_assisted_vessel_id = fields.Many2one("sedar.client.vessel", string="Assisted Vessel Interest", ondelete="set null")
    sedar_service_order_id = fields.Many2one("sedar.marine.service.order", string="Resulting Service Order", ondelete="set null")
    sedar_service_interest = fields.Char(string="Marine Service Interest")
    sedar_demo_only = fields.Boolean(default=True, readonly=True)


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_ensure_erp_demo(self):
        env = self.env
        company = env.company
        employees = env["hr.employee"].search([
            ("company_id", "=", company.id), ("name", "!=", "Administrator"),
        ], order="id", limit=3)
        if not employees:
            return True

        # Standard Attendance records are the source facts for the demonstration payroll view.
        attendance = env["hr.attendance"]
        for index, employee in enumerate(employees):
            for day in (3, 4):
                check_in = datetime(2026, 8, day, 8, 0)
                if not attendance.search([("employee_id", "=", employee.id), ("check_in", "=", check_in)], limit=1):
                    attendance.create({"employee_id": employee.id, "check_in": check_in, "check_out": datetime(2026, 8, day, 17, 0)})

        reviewer = env.user
        for index, employee in enumerate(employees):
            _record(env, "sedar.hr.performance.review", f"performance_review_{index + 1}", {
                "name": f"Demo 2026 Mid-Year Review - {employee.name}", "employee_id": employee.id,
                "reviewer_id": reviewer.id, "period_start": "2026-01-01", "period_end": "2026-06-30",
                "review_date": "2026-07-15", "state": "approved", "rating": "meets",
                "strengths": "Reliable attendance and strong operational discipline in the fictional demo.",
                "development_goals": "Continue technical refresher training and leadership coaching.",
                "manager_summary": "Demonstration-only performance history; not an approved SEDAR appraisal policy.",
            })
            crew_profile = env["sedar.crew.profile"].search([("employee_id", "=", employee.id)], limit=1)
            worked_hours = sum(env["hr.attendance"].search([
                ("employee_id", "=", employee.id), ("check_in", ">=", "2026-08-01 00:00:00"),
                ("check_in", "<", "2026-08-16 00:00:00"),
            ]).mapped("worked_hours"))
            approved_leave_hours = sum(env["hr.leave"].search([
                ("employee_id", "=", employee.id), ("state", "=", "validate"),
                ("request_date_from", ">=", "2026-08-01"), ("request_date_to", "<=", "2026-08-15"),
            ]).mapped("number_of_hours"))
            _record(env, "sedar.hr.payroll.input", f"payroll_input_{index + 1}", {
                "name": f"Demo August Payroll Inputs - {employee.name}", "employee_id": employee.id,
                "period_start": "2026-08-01", "period_end": "2026-08-15", "attendance_hours": worked_hours,
                "approved_leave_hours": approved_leave_hours, "eligible_crew_days": 2 if crew_profile and crew_profile.availability_status == "available" else 0,
                "source_note": "Derived from standard Odoo Attendance, approved Time Off, and eligible Crew Profile facts. Payroll calculation and Philippine statutory compliance are deferred.",
            })

        department = employees[0].department_id
        tugboat = env["sedar.tugboat"].search([], order="id", limit=1)
        currency = company.currency_id
        _record(env, "sedar.finance.budget", "budget_demo_operations", {
            "name": "DEMO 2026 Marine Operations Budget", "department_id": department.id,
            "tugboat_id": tugboat.id, "date_from": "2026-01-01", "date_to": "2026-12-31",
            "currency_id": currency.id, "planned_amount": 1250000, "actual_amount": 438500,
            "note": "Demonstration-only budget-versus-actual source; replace with SEDAR-approved budget policy.",
        })
        if tugboat:
            _record(env, "sedar.fixed.asset", "asset_demo_tugboat", {
                "name": f"DEMO Fixed Asset - {tugboat.name}", "tugboat_id": tugboat.id,
                "acquisition_date": "2024-01-01", "currency_id": currency.id,
                "original_value": 18000000, "residual_value": 1800000, "useful_life_months": 180,
            })

        self._sedar_ensure_accounting_demo(company)
        self._sedar_ensure_crm_demo(company)
        return True

    def _sedar_ensure_accounting_demo(self, company):
        env = self.env
        client = env["res.partner"].search([("is_company", "=", True)], order="id", limit=1)
        if not client:
            return
        sale_journal = env["account.journal"].search([("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
        purchase_journal = env["account.journal"].search([("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1)
        income = env["account.account"].search([("account_type", "=", "income")], limit=1)
        expense = env["account.account"].search([("account_type", "=", "expense")], limit=1)
        product = env.ref("sedar_marine_finance.product_marine_service", raise_if_not_found=False)
        if sale_journal and income and product and not env["account.move"].search([("ref", "=", "SEDAR-ERP-DEMO-SALE")], limit=1):
            invoice = env["account.move"].create({
                "move_type": "out_invoice", "partner_id": client.id, "journal_id": sale_journal.id,
                "invoice_date": "2026-08-05", "ref": "SEDAR-ERP-DEMO-SALE",
                "invoice_line_ids": [Command.create({"product_id": product.id, "name": "Demo tug assistance", "quantity": 4, "price_unit": 4500, "account_id": income.id})],
            })
            invoice.action_post()
        if purchase_journal and expense and not env["account.move"].search([("ref", "=", "SEDAR-ERP-DEMO-BILL")], limit=1):
            vendor = _record(env, "res.partner", "vendor_demo_marine_parts", {
                "name": "Demo Marine Parts Supplier", "supplier_rank": 1, "company_id": company.id,
            })
            bill = env["account.move"].create({
                "move_type": "in_invoice", "partner_id": vendor.id, "journal_id": purchase_journal.id,
                "invoice_date": "2026-08-05", "ref": "SEDAR-ERP-DEMO-BILL",
                "invoice_line_ids": [Command.create({"name": "Demo maintenance parts", "quantity": 1, "price_unit": 18500, "account_id": expense.id})],
            })
            bill.action_post()

    def _sedar_ensure_crm_demo(self, company):
        env = self.env
        client = env["res.partner"].search([("is_company", "=", True)], order="id", limit=1)
        order = env["sedar.marine.service.order"].search([], order="id", limit=1)
        if not client or not order or env["crm.lead"].search([("sedar_demo_only", "=", True)], limit=1):
            return
        stage = env["crm.stage"].search([("is_won", "=", True)], limit=1) or env["crm.stage"].search([], limit=1)
        vessel = order.assisted_vessel_id
        opportunity = env["crm.lead"].create({
            "name": "Demo Port Expansion Tug Assist Opportunity", "type": "opportunity", "partner_id": client.id,
            "stage_id": stage.id, "expected_revenue": 85000, "description": "Demonstration opportunity for recurring harbor assistance.",
            "sedar_assisted_vessel_id": vessel.id, "sedar_service_order_id": order.id,
            "sedar_service_interest": order.service_type_id.name, "team_id": env["crm.team"].search([], limit=1).id,
        })
        activity_type = env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model_id = env["ir.model"]._get_id("crm.lead")
        if activity_type:
            env["mail.activity"].create({
                "activity_type_id": activity_type.id, "res_model_id": model_id, "res_id": opportunity.id,
                "user_id": env.user.id, "summary": "Confirm recurring tug assistance requirement",
                "note": "Follow up with the client before creating the next Service Order.", "date_deadline": "2026-08-12",
            })

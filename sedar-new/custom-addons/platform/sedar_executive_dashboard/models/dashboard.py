from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .res_users import EXECUTIVE_DASHBOARD_VIEWS


MODULE = "sedar_executive_dashboard"


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


class SedarExecutiveDashboard(models.Model):
    _name = "sedar.executive.dashboard"
    _description = "SEDAR Executive Management Dashboard"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, ondelete="restrict")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    dashboard_perspective = fields.Selection(
        EXECUTIVE_DASHBOARD_VIEWS,
        compute="_compute_dashboard_perspective",
    )
    perspective_title = fields.Char(compute="_compute_dashboard_perspective")
    perspective_summary = fields.Char(compute="_compute_dashboard_perspective")
    visible_attention_count = fields.Integer(compute="_compute_dashboard_perspective")
    last_refreshed = fields.Datetime(compute="_compute_kpis")
    revenue_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    invoiced_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    unpaid_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    cash_collected_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    known_cost_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    service_order_count = fields.Integer(compute="_compute_kpis")
    active_service_order_count = fields.Integer(compute="_compute_kpis")
    completed_service_order_count = fields.Integer(compute="_compute_kpis")
    marine_operation_count = fields.Integer(compute="_compute_kpis")
    fleet_count = fields.Integer(compute="_compute_kpis")
    available_tug_count = fields.Integer(compute="_compute_kpis")
    tug_blocker_count = fields.Integer(compute="_compute_kpis")
    utilization_percent = fields.Float(compute="_compute_kpis")
    crew_count = fields.Integer(compute="_compute_kpis")
    available_crew_count = fields.Integer(compute="_compute_kpis")
    vacancy_count = fields.Integer(compute="_compute_kpis")
    applicant_count = fields.Integer(compute="_compute_kpis")
    open_shortage_count = fields.Integer(compute="_compute_kpis")
    credential_expiry_count = fields.Integer(compute="_compute_kpis")
    maintenance_open_count = fields.Integer(compute="_compute_kpis")
    maintenance_blocker_count = fields.Integer(compute="_compute_kpis")
    drydock_active_count = fields.Integer(compute="_compute_kpis")
    inventory_shortage_count = fields.Integer(compute="_compute_kpis")
    fuel_consumed_qty = fields.Float(compute="_compute_kpis")
    purchase_open_count = fields.Integer(compute="_compute_kpis")
    purchase_overdue_count = fields.Integer(compute="_compute_kpis")
    hsse_incident_count = fields.Integer(compute="_compute_kpis")
    hsse_high_risk_count = fields.Integer(compute="_compute_kpis")
    hsse_permit_exception_count = fields.Integer(compute="_compute_kpis")
    hsse_overdue_action_count = fields.Integer(compute="_compute_kpis")
    document_expiry_count = fields.Integer(compute="_compute_kpis")
    governance_exception_count = fields.Integer(compute="_compute_kpis")
    reporting_date = fields.Date(compute="_compute_kpis")
    current_month_revenue = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    overdue_receivable_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    overdue_receivable_count = fields.Integer(compute="_compute_kpis")
    payable_30_day_total = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    payable_30_day_count = fields.Integer(compute="_compute_kpis")
    billing_review_count = fields.Integer(compute="_compute_kpis")
    blocked_service_order_count = fields.Integer(compute="_compute_kpis")
    cancelled_service_order_count = fields.Integer(compute="_compute_kpis")
    attention_total_count = fields.Integer(compute="_compute_kpis")
    profitability_note = fields.Char(compute="_compute_kpis")
    utilization_note = fields.Char(compute="_compute_kpis")

    @api.depends_context("uid")
    def _compute_dashboard_perspective(self):
        perspective = self.env.user.sedar_executive_dashboard_view or "owner"
        presentations = {
            "owner": (
                "Owner Overview",
                "Company-wide operating health across vessels, people, cash, and customers.",
            ),
            "operations": (
                "Operations",
                "Fleet readiness, Service Order delivery, maintenance, inventory, and procurement.",
            ),
            "finance": (
                "Finance",
                "Revenue, collections, receivables, payables, and billing decisions.",
            ),
            "people": (
                "Crewing & Safety",
                "Crew readiness, credential risk, shortages, vacancies, and HSSE follow-through.",
            ),
        }
        for dashboard in self:
            dashboard.dashboard_perspective = perspective
            dashboard.perspective_title, dashboard.perspective_summary = presentations[perspective]
            dashboard.visible_attention_count = dashboard._perspective_attention_count(
                perspective
            )

    def _perspective_attention_count(self, perspective):
        self.ensure_one()
        if perspective == "operations":
            return sum([
                self.blocked_service_order_count,
                self.maintenance_blocker_count,
                self.inventory_shortage_count,
                self.purchase_overdue_count,
                self.document_expiry_count,
            ])
        if perspective == "finance":
            return self.overdue_receivable_count + self.billing_review_count
        if perspective == "people":
            return sum([
                self.credential_expiry_count,
                self.open_shortage_count,
                self.hsse_overdue_action_count,
            ])
        return self.attention_total_count

    def action_set_dashboard_perspective(self):
        self.ensure_one()
        perspective = self.env.context.get("dashboard_perspective")
        allowed = dict(EXECUTIVE_DASHBOARD_VIEWS)
        if perspective not in allowed:
            raise UserError(_("Select a valid executive dashboard view."))
        self.env.user.write({"sedar_executive_dashboard_view": perspective})
        return {
            "type": "ir.actions.act_window",
            "name": _("Company Dashboard"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _assign_people_and_support_kpis(self, today, warning):
        company_domain = [("company_id", "=", self.company_id.id)]
        profiles = self.env["sedar.crew.profile"].sudo().search([])
        requests = self.env["maintenance.request"].sudo().search([
            ("sedar_tugboat_id", "!=", False), ("done", "=", False)
        ])
        purchases = self.env["sedar.purchase.request"].sudo().search(company_domain + [
            ("state", "in", ["submitted", "approved"])
        ])
        self.crew_count = len(profiles)
        self.available_crew_count = len(profiles.filtered(
            lambda profile: profile.availability_status in ("available", "assigned")
        ))
        self.vacancy_count = self.env["sedar.job.vacancy"].sudo().search_count([
            ("state", "!=", "filled")
        ])
        self.applicant_count = self.env["hr.applicant"].sudo().search_count([])
        self.open_shortage_count = self.env["sedar.crew.shortage"].sudo().search_count(company_domain + [
            ("status", "=", "open")
        ])
        self.credential_expiry_count = self.env["sedar.crew.certificate"].sudo().search_count([
            ("expiry_date", "<=", warning)
        ])
        self.maintenance_open_count = len(requests)
        self.maintenance_blocker_count = len(
            requests.filtered("sedar_blocks_tug_readiness")
        )
        self.drydock_active_count = self.env["sedar.drydock.plan"].sudo().search_count([
            ("state", "in", ["planned", "in_progress"])
        ])
        self.inventory_shortage_count = self.env["sedar.inventory.requirement"].sudo().search_count(company_domain + [
            ("readiness_state", "!=", "ready")
        ])
        fuel = self.env["sedar.operation.fuel.log"].sudo().search(company_domain + [
            ("state", "=", "consumed")
        ])
        self.fuel_consumed_qty = sum(fuel.mapped("consumed_qty"))
        self.purchase_open_count = len(purchases)
        self.purchase_overdue_count = len(purchases.filtered(
            lambda purchase: purchase.required_date and purchase.required_date.date() < today
        ))
        self.hsse_incident_count = self.env["sedar.hsse.incident"].sudo().search_count([
            ("state", "in", ["reported", "investigating", "action_required"])
        ])
        self.hsse_high_risk_count = self.env["sedar.hsse.risk.assessment"].sudo().search_count([
            ("residual_risk_level", "in", ["high", "critical"])
        ])
        self.hsse_permit_exception_count = self.env["sedar.hsse.permit"].sudo().search_count([
            ("operational_exception", "=", True)
        ])
        self.hsse_overdue_action_count = self.env["sedar.hsse.corrective.action"].sudo().search_count([
            ("is_overdue", "=", True)
        ])
        self.document_expiry_count = self.env["sedar.document"].sudo().search_count([
            ("valid_until", "<=", warning), ("state", "=", "active")
        ])
        self.governance_exception_count = self.env["sedar.corporate.record"].sudo().search_count([
            ("compliance_status", "in", ["expired", "renewal_due"])
        ])

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_kpis(self):
        today = fields.Date.context_today(self)
        warning = fields.Date.add(today, days=30)
        month_start = today.replace(day=1)
        for dashboard in self:
            env = self.env
            moves = env["account.move"].sudo().search([("company_id", "=", dashboard.company_id.id), ("state", "=", "posted")])
            sales = moves.filtered(lambda move: move.move_type in ("out_invoice", "out_refund"))
            bills = moves.filtered(lambda move: move.move_type in ("in_invoice", "in_refund"))
            invoices = sales.filtered(lambda move: move.move_type == "out_invoice")
            month_sales = sales.filtered(
                lambda move: move.invoice_date and month_start <= move.invoice_date <= today
            )
            overdue = invoices.filtered(
                lambda move: move.amount_residual_signed > 0
                and move.invoice_date_due and move.invoice_date_due < today
            )
            payable_30_day = bills.filtered(
                lambda move: move.move_type == "in_invoice"
                and move.amount_residual_signed < 0
                and move.invoice_date_due and move.invoice_date_due <= warning
            )
            company_domain = [("company_id", "=", dashboard.company_id.id)]
            orders = env["sedar.marine.service.order"].sudo().search(company_domain)
            operations = env["sedar.marine.operation"].sudo().search(company_domain)
            assignments = env["sedar.tug.assignment"].sudo().search(
                company_domain + [("actual_start", "!=", False), ("actual_end", "!=", False)]
            )
            actual_hours = sum((line.actual_end - line.actual_start).total_seconds() / 3600 for line in assignments)
            planned_hours = sum(max((line.planned_end - line.planned_start).total_seconds() / 3600, 0) for line in assignments if line.planned_start and line.planned_end)
            tugs = env["sedar.tugboat"].sudo().search([])
            dashboard.revenue_total = sum(sales.mapped("amount_total"))
            dashboard.invoiced_total = dashboard.revenue_total
            dashboard.unpaid_total = sum(sales.mapped("amount_residual"))
            dashboard.cash_collected_total = sum(sales.mapped("amount_paid"))
            dashboard.known_cost_total = sum(bills.mapped("amount_total"))
            dashboard.reporting_date = today
            dashboard.last_refreshed = fields.Datetime.now()
            dashboard.current_month_revenue = sum(month_sales.mapped("amount_total_signed"))
            dashboard.overdue_receivable_total = sum(overdue.mapped("amount_residual_signed"))
            dashboard.overdue_receivable_count = len(overdue)
            dashboard.payable_30_day_total = abs(sum(payable_30_day.mapped("amount_residual_signed")))
            dashboard.payable_30_day_count = len(payable_30_day)
            dashboard.service_order_count = len(orders)
            dashboard.active_service_order_count = len(orders.filtered(lambda order: order.state not in ("completed", "billing_ready", "closed", "cancelled")))
            dashboard.completed_service_order_count = len(orders.filtered(lambda order: order.state in ("completed", "billing_ready", "closed")))
            dashboard.marine_operation_count = len(operations)
            dashboard.fleet_count = len(tugs)
            dashboard.available_tug_count = len(tugs.filtered(lambda tug: tug.availability_status == "available"))
            dashboard.tug_blocker_count = len(tugs.filtered(lambda tug: tug.availability_status not in ("available", "assigned")))
            dashboard.utilization_percent = actual_hours / planned_hours * 100 if planned_hours else 0
            dashboard._assign_people_and_support_kpis(today, warning)
            dashboard.billing_review_count = len(orders.filtered(
                lambda order: order.billing_status in ("review", "pricing_exception")
            ))
            dashboard.blocked_service_order_count = len(orders.filtered(lambda order: order.state == "blocked"))
            dashboard.cancelled_service_order_count = len(orders.filtered(lambda order: order.state == "cancelled"))
            dashboard.attention_total_count = sum([
                dashboard.overdue_receivable_count,
                dashboard.billing_review_count,
                dashboard.blocked_service_order_count,
                dashboard.credential_expiry_count,
                dashboard.maintenance_blocker_count,
                dashboard.inventory_shortage_count,
                dashboard.purchase_overdue_count,
                dashboard.hsse_overdue_action_count,
                dashboard.document_expiry_count,
            ])
            dashboard.profitability_note = _(
                "Revenue and known posted costs are shown separately. Job margin awaits approved cost-allocation rules."
            )
            dashboard.utilization_note = _(
                "Fleet utilization is intentionally not reported until management approves the time and availability definition."
            )

    def _open(self, model, domain, name=None):
        return {
            "type": "ir.actions.act_window",
            "name": name or _("Dashboard Source Records"),
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain,
            "target": "current",
        }

    def action_open_invoices(self): return self._open("account.move", [("company_id", "=", self.company_id.id), ("state", "=", "posted"), ("move_type", "in", ["out_invoice", "out_refund"])])
    def action_open_service_orders(self): return self._open("sedar.marine.service.order", [("company_id", "=", self.company_id.id)])
    def action_open_tugs(self): return self._open("sedar.tugboat", [])
    def action_open_crew(self): return self._open("sedar.crew.profile", [])
    def action_open_maintenance(self): return self._open("maintenance.request", [("done", "=", False)])
    def action_open_inventory(self): return self._open("sedar.inventory.requirement", [("company_id", "=", self.company_id.id), ("readiness_state", "!=", "ready")])
    def action_open_procurement(self): return self._open("sedar.purchase.request", [("company_id", "=", self.company_id.id), ("state", "in", ["submitted", "approved"])])
    def action_open_hsse(self):
        return self._open("sedar.hsse.incident", [
            ("state", "in", ["reported", "investigating", "action_required"]),
        ])
    def action_open_documents(self): return self._open("sedar.document", [("state", "=", "active")])
    def action_open_governance(self): return self._open("sedar.corporate.record", [])

    def action_open_overdue_receivables(self):
        today = fields.Date.context_today(self)
        return self._open("account.move", [
            ("company_id", "=", self.company_id.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<", today),
        ], _("Overdue Customer Invoices"))

    def action_open_upcoming_payables(self):
        warning = fields.Date.add(fields.Date.context_today(self), days=30)
        return self._open("account.move", [
            ("company_id", "=", self.company_id.id),
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<=", warning),
        ], _("Vendor Bills Due Within 30 Days"))

    def action_open_billing_reviews(self):
        return self._open("sedar.marine.service.order", [
            ("company_id", "=", self.company_id.id),
            ("billing_status", "in", ["review", "pricing_exception"]),
        ], _("Billing Reviews and Pricing Exceptions"))

    def action_open_blocked_service_orders(self):
        return self._open("sedar.marine.service.order", [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "blocked"),
        ], _("Blocked Service Orders"))

    def action_open_credential_expiries(self):
        warning = fields.Date.add(fields.Date.context_today(self), days=30)
        return self._open("sedar.crew.certificate", [
            ("expiry_date", "<=", warning),
        ], _("Crew Credentials Requiring Attention"))

    def action_open_maintenance_blockers(self):
        return self._open("maintenance.request", [
            ("sedar_tugboat_id", "!=", False),
            ("sedar_blocks_tug_readiness", "=", True),
        ], _("Maintenance Readiness Blockers"))

    def action_open_overdue_hsse_actions(self):
        return self._open("sedar.hsse.corrective.action", [
            ("is_overdue", "=", True),
        ], _("Overdue HSSE Corrective Actions"))

    def action_open_expiring_documents(self):
        warning = fields.Date.add(fields.Date.context_today(self), days=30)
        return self._open("sedar.document", [
            ("state", "=", "active"),
            ("valid_until", "<=", warning),
        ], _("Documents Requiring Renewal"))

    def action_open_flagship_service(self):
        self.ensure_one()
        order = self.env["sedar.marine.service.order"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("state", "in", ["completed", "billing_ready", "closed"]),
            ("invoice_count", ">", 0),
        ], order="requested_start desc, id desc", limit=1)
        if not order:
            return self.action_open_service_orders()
        return {
            "type": "ir.actions.act_window",
            "name": _("Completed Service to Payment Walkthrough"),
            "res_model": order._name,
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }

from odoo import api, fields, models


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
    last_refreshed = fields.Datetime(readonly=True)
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

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_kpis(self):
        today = fields.Date.context_today(self)
        warning = fields.Date.add(today, days=30)
        for dashboard in self:
            env = self.env
            moves = env["account.move"].sudo().search([("company_id", "=", dashboard.company_id.id), ("state", "=", "posted")])
            sales = moves.filtered(lambda move: move.move_type in ("out_invoice", "out_refund"))
            bills = moves.filtered(lambda move: move.move_type in ("in_invoice", "in_refund"))
            orders = env["sedar.marine.service.order"].sudo().search([])
            operations = env["sedar.marine.operation"].sudo().search([])
            assignments = env["sedar.tug.assignment"].sudo().search([("actual_start", "!=", False), ("actual_end", "!=", False)])
            actual_hours = sum((line.actual_end - line.actual_start).total_seconds() / 3600 for line in assignments)
            planned_hours = sum(max((line.planned_end - line.planned_start).total_seconds() / 3600, 0) for line in assignments if line.planned_start and line.planned_end)
            tugs = env["sedar.tugboat"].sudo().search([])
            profiles = env["sedar.crew.profile"].sudo().search([])
            certificates = env["sedar.crew.certificate"].sudo().search([("expiry_date", "<=", warning)])
            requests = env["maintenance.request"].sudo().search([("sedar_tugboat_id", "!=", False), ("done", "=", False)])
            drydocks = env["sedar.drydock.plan"].sudo().search([("state", "in", ["planned", "in_progress"])])
            inventory = env["sedar.inventory.requirement"].sudo().search([("readiness_state", "=", "shortage")])
            fuel = env["sedar.operation.fuel.log"].sudo().search([("state", "=", "consumed")])
            purchases = env["sedar.purchase.request"].sudo().search([("state", "in", ["submitted", "approved"])])
            incidents = env["sedar.hsse.incident"].sudo().search([("state", "in", ["open", "investigating"])])
            risks = env["sedar.hsse.risk.assessment"].sudo().search([("residual_risk_level", "in", ["high", "critical"])])
            permits = env["sedar.hsse.permit"].sudo().search([("operational_exception", "=", True)])
            actions = env["sedar.hsse.corrective.action"].sudo().search([("is_overdue", "=", True)])
            documents = env["sedar.document"].sudo().search([("valid_until", "<=", warning), ("state", "=", "active")])
            corporate = env["sedar.corporate.record"].sudo().search([("compliance_status", "in", ["expired", "renewal_due"])])
            vacancies = env["sedar.job.vacancy"].sudo().search([("state", "!=", "filled")])
            shortages = env["sedar.crew.shortage"].sudo().search([("status", "=", "open")])
            dashboard.revenue_total = sum(sales.mapped("amount_total"))
            dashboard.invoiced_total = dashboard.revenue_total
            dashboard.unpaid_total = sum(sales.mapped("amount_residual"))
            dashboard.cash_collected_total = sum(sales.mapped("amount_paid"))
            dashboard.known_cost_total = sum(bills.mapped("amount_total"))
            dashboard.service_order_count = len(orders)
            dashboard.active_service_order_count = len(orders.filtered(lambda order: order.state not in ("completed", "billing_ready", "closed", "cancelled")))
            dashboard.completed_service_order_count = len(orders.filtered(lambda order: order.state in ("completed", "billing_ready", "closed")))
            dashboard.marine_operation_count = len(operations)
            dashboard.fleet_count = len(tugs)
            dashboard.available_tug_count = len(tugs.filtered(lambda tug: tug.availability_status == "available"))
            dashboard.tug_blocker_count = len(tugs.filtered(lambda tug: tug.availability_status not in ("available", "assigned")))
            dashboard.utilization_percent = actual_hours / planned_hours * 100 if planned_hours else 0
            dashboard.crew_count = len(profiles)
            dashboard.available_crew_count = len(profiles.filtered(lambda profile: profile.availability_status in ("available", "assigned")))
            dashboard.vacancy_count = len(vacancies)
            dashboard.applicant_count = env["hr.applicant"].sudo().search_count([])
            dashboard.open_shortage_count = len(shortages)
            dashboard.credential_expiry_count = len(certificates)
            dashboard.maintenance_open_count = len(requests)
            dashboard.maintenance_blocker_count = len(requests.filtered("sedar_blocks_tug_readiness"))
            dashboard.drydock_active_count = len(drydocks)
            dashboard.inventory_shortage_count = len(inventory)
            dashboard.fuel_consumed_qty = sum(fuel.mapped("consumed_qty"))
            dashboard.purchase_open_count = len(purchases)
            dashboard.purchase_overdue_count = len(purchases.filtered(lambda request: request.required_date and request.required_date.date() < today))
            dashboard.hsse_incident_count = len(incidents)
            dashboard.hsse_high_risk_count = len(risks)
            dashboard.hsse_permit_exception_count = len(permits)
            dashboard.hsse_overdue_action_count = len(actions)
            dashboard.document_expiry_count = len(documents)
            dashboard.governance_exception_count = len(corporate)

    def _open(self, model, domain):
        return {"type": "ir.actions.act_window", "name": "Dashboard Source Records", "res_model": model, "view_mode": "list,form", "domain": domain, "target": "current"}

    def action_open_invoices(self): return self._open("account.move", [("state", "=", "posted"), ("move_type", "in", ["out_invoice", "out_refund"])])
    def action_open_service_orders(self): return self._open("sedar.marine.service.order", [])
    def action_open_tugs(self): return self._open("sedar.tugboat", [])
    def action_open_crew(self): return self._open("sedar.crew.profile", [])
    def action_open_maintenance(self): return self._open("maintenance.request", [("done", "=", False)])
    def action_open_inventory(self): return self._open("sedar.inventory.requirement", [("readiness_state", "=", "shortage")])
    def action_open_procurement(self): return self._open("sedar.purchase.request", [("state", "in", ["submitted", "approved"])])
    def action_open_hsse(self): return self._open("sedar.hsse.incident", [("state", "in", ["open", "investigating"])])
    def action_open_documents(self): return self._open("sedar.document", [("state", "=", "active")])
    def action_open_governance(self): return self._open("sedar.corporate.record", [])


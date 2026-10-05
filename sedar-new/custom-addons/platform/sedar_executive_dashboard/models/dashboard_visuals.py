from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools import date_utils


def _compact_number(value):
    amount = abs(value)
    if amount >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:,.0f}"


def _width(value, maximum):
    if not maximum or value <= 0:
        return 0
    return min(round(value / maximum * 100, 1), 100)


def _bar_chart(title, kicker, subtitle, rows, maximum=None):
    scale = maximum if maximum is not None else max((row[1] for row in rows), default=0)
    bars = []
    for label, value, display, tone in rows:
        bars.append(Markup(
            '<div class="sedar_chart_row">'
            '<div class="sedar_chart_label"><span>{}</span><strong>{}</strong></div>'
            '<div class="sedar_chart_track" role="img" aria-label="{}: {}">'
            '<i class="sedar_chart_fill sedar_chart_fill_{}" style="width: {}%"></i>'
            '</div></div>'
        ).format(
            escape(label), escape(display), escape(label), escape(display),
            escape(tone), _width(value, scale),
        ))
    return Markup(
        '<section class="sedar_chart_card">'
        '<header><span>{}</span><h3>{}</h3><p>{}</p></header>'
        '<div class="sedar_chart_body">{}</div></section>'
    ).format(escape(kicker), escape(title), escape(subtitle), Markup("").join(bars))


def _trend_chart(rows, currency_symbol):
    maximum = max((max(revenue, cost) for _, revenue, cost in rows), default=0)
    chart_rows = []
    for label, revenue, cost in rows:
        chart_rows.append(Markup(
            '<div class="sedar_trend_row">'
            '<span>{}</span><div class="sedar_trend_bars">'
            '<i class="sedar_chart_fill_blue" style="width: {}%"></i>'
            '<i class="sedar_chart_fill_slate" style="width: {}%"></i>'
            '</div><strong>{}{}</strong></div>'
        ).format(
            escape(label), _width(revenue, maximum), _width(cost, maximum),
            escape(currency_symbol), escape(_compact_number(revenue)),
        ))
    return Markup(
        '<section class="sedar_chart_card sedar_chart_card_wide">'
        '<header><span>6-MONTH TREND</span><h3>Revenue and known costs</h3>'
        '<p>Net posted customer invoices compared with posted vendor bills.</p></header>'
        '<div class="sedar_chart_legend"><i class="sedar_chart_fill_blue"></i>Revenue'
        '<i class="sedar_chart_fill_slate"></i>Known costs</div>'
        '<div class="sedar_trend_body">{}</div></section>'
    ).format(Markup("").join(chart_rows))


class SedarExecutiveDashboardVisuals(models.Model):
    _inherit = "sedar.executive.dashboard"

    visualization_html = fields.Html(
        compute="_compute_visualization_html",
        sanitize=False,
    )

    def _monthly_finance_rows(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        first_month = date_utils.start_of(today, "month")
        starts = [date_utils.subtract(first_month, months=offset) for offset in range(5, -1, -1)]
        moves = self.env["account.move"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("invoice_date", ">=", starts[0]),
            ("move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"]),
        ])
        rows = []
        for start in starts:
            end = date_utils.end_of(start, "month")
            monthly = moves.filtered(
                lambda move, month_start=start, month_end=end:
                move.invoice_date and month_start <= move.invoice_date <= month_end
            )
            revenue = sum(monthly.filtered(
                lambda move: move.move_type in ("out_invoice", "out_refund")
            ).mapped("amount_total_signed"))
            cost = abs(sum(monthly.filtered(
                lambda move: move.move_type in ("in_invoice", "in_refund")
            ).mapped("amount_total_signed")))
            rows.append((start.strftime("%b"), max(revenue, 0), cost))
        return rows

    def _money(self, value):
        symbol = self.currency_id.symbol or self.currency_id.name or ""
        return f"{symbol}{_compact_number(value)}"

    def _owner_charts(self):
        assigned = max(self.fleet_count - self.available_tug_count - self.tug_blocker_count, 0)
        risk_rows = [
            ("Overdue invoices", self.overdue_receivable_count, f"{self.overdue_receivable_count} invoices", "red"),
            ("Maintenance holds", self.maintenance_blocker_count, f"{self.maintenance_blocker_count} vessels", "orange"),
            ("Crew credentials", self.credential_expiry_count, f"{self.credential_expiry_count} due", "amber"),
            ("Inventory shortages", self.inventory_shortage_count, f"{self.inventory_shortage_count} requirements", "purple"),
        ]
        return [
            _trend_chart(self._monthly_finance_rows(), self.currency_id.symbol or ""),
            _bar_chart("Fleet readiness", "VESSELS", "Share of the fleet available, assigned, or blocked.", [
                ("Available", self.available_tug_count, f"{self.available_tug_count} of {self.fleet_count}", "green"),
                ("Assigned", assigned, f"{assigned} of {self.fleet_count}", "blue"),
                ("Unavailable", self.tug_blocker_count, f"{self.tug_blocker_count} of {self.fleet_count}", "red"),
            ], self.fleet_count),
            _bar_chart("Service delivery", "CUSTOMERS", "Current workload compared with all Service Orders.", [
                ("Active", self.active_service_order_count, f"{self.active_service_order_count} orders", "blue"),
                ("Completed", self.completed_service_order_count, f"{self.completed_service_order_count} orders", "green"),
                ("Blocked", self.blocked_service_order_count, f"{self.blocked_service_order_count} orders", "red"),
                ("Cancelled", self.cancelled_service_order_count, f"{self.cancelled_service_order_count} orders", "slate"),
            ], self.service_order_count),
            _bar_chart("Risk concentration", "ATTENTION", "Longer bars identify where management attention is concentrated.", risk_rows),
        ]

    def _operations_charts(self):
        assigned = max(self.fleet_count - self.available_tug_count - self.tug_blocker_count, 0)
        return [
            _bar_chart("Fleet readiness", "VESSELS", "Immediate ability to accept and execute work.", [
                ("Available", self.available_tug_count, f"{self.available_tug_count} vessels", "green"),
                ("Assigned", assigned, f"{assigned} vessels", "blue"),
                ("Unavailable", self.tug_blocker_count, f"{self.tug_blocker_count} vessels", "red"),
            ], self.fleet_count),
            _bar_chart("Service workflow", "DELIVERY", "Operational progress across the Service Order portfolio.", [
                ("Active", self.active_service_order_count, f"{self.active_service_order_count} orders", "blue"),
                ("Completed", self.completed_service_order_count, f"{self.completed_service_order_count} orders", "green"),
                ("Blocked", self.blocked_service_order_count, f"{self.blocked_service_order_count} orders", "red"),
            ], self.service_order_count),
            _bar_chart("Readiness blockers", "EXCEPTIONS", "Sources preventing work or vessel release.", [
                ("Service blocks", self.blocked_service_order_count, f"{self.blocked_service_order_count} orders", "red"),
                ("Maintenance holds", self.maintenance_blocker_count, f"{self.maintenance_blocker_count} holds", "orange"),
                ("Inventory", self.inventory_shortage_count, f"{self.inventory_shortage_count} shortages", "purple"),
                ("Documents", self.document_expiry_count, f"{self.document_expiry_count} renewals", "amber"),
            ]),
            _bar_chart("Support workload", "CAPACITY", "Open supporting work that Operations must coordinate.", [
                ("Maintenance", self.maintenance_open_count, f"{self.maintenance_open_count} open", "orange"),
                ("Purchasing", self.purchase_open_count, f"{self.purchase_open_count} open", "blue"),
                ("Purchasing overdue", self.purchase_overdue_count, f"{self.purchase_overdue_count} overdue", "red"),
                ("Dry-dock plans", self.drydock_active_count, f"{self.drydock_active_count} active", "slate"),
            ]),
        ]

    def _finance_charts(self):
        return [
            _trend_chart(self._monthly_finance_rows(), self.currency_id.symbol or ""),
            _bar_chart("Cash conversion", "COLLECTIONS", "How posted customer billing converts into cash.", [
                ("Invoiced", self.invoiced_total, self._money(self.invoiced_total), "blue"),
                ("Collected", self.cash_collected_total, self._money(self.cash_collected_total), "green"),
                ("Still unpaid", self.unpaid_total, self._money(self.unpaid_total), "orange"),
                ("Already overdue", self.overdue_receivable_total, self._money(self.overdue_receivable_total), "red"),
            ], max(self.invoiced_total, self.cash_collected_total, 1)),
            _bar_chart("Billing pipeline", "SERVICE TO CASH", "Completed work and exceptions waiting before collection.", [
                ("Completed services", self.completed_service_order_count, f"{self.completed_service_order_count} orders", "green"),
                ("Billing decisions", self.billing_review_count, f"{self.billing_review_count} reviews", "amber"),
                ("Blocked services", self.blocked_service_order_count, f"{self.blocked_service_order_count} orders", "red"),
                ("Overdue invoices", self.overdue_receivable_count, f"{self.overdue_receivable_count} invoices", "orange"),
            ]),
            _bar_chart("Financial pressure", "NEXT DECISIONS", "Relative size of current obligations and exposure.", [
                ("Overdue receivables", self.overdue_receivable_total, self._money(self.overdue_receivable_total), "red"),
                ("Payables due in 30 days", self.payable_30_day_total, self._money(self.payable_30_day_total), "orange"),
                ("Known posted costs", self.known_cost_total, self._money(self.known_cost_total), "slate"),
            ]),
        ]

    def _people_charts(self):
        unavailable = max(self.crew_count - self.available_crew_count, 0)
        return [
            _bar_chart("Crew availability", "READINESS", "Crew currently available or assigned compared with all profiles.", [
                ("Ready", self.available_crew_count, f"{self.available_crew_count} of {self.crew_count}", "green"),
                ("Unavailable", unavailable, f"{unavailable} of {self.crew_count}", "red"),
            ], self.crew_count),
            _bar_chart("Staffing pipeline", "CAPACITY", "Demand and the available recruitment pipeline.", [
                ("Crew profiles", self.crew_count, f"{self.crew_count} people", "blue"),
                ("Applicants", self.applicant_count, f"{self.applicant_count} candidates", "green"),
                ("Vacancies", self.vacancy_count, f"{self.vacancy_count} openings", "orange"),
                ("Open shortages", self.open_shortage_count, f"{self.open_shortage_count} shortages", "red"),
            ]),
            _bar_chart("Compliance exposure", "CREDENTIALS", "People-related records requiring follow-through.", [
                ("Credentials due", self.credential_expiry_count, f"{self.credential_expiry_count} due", "amber"),
                ("Crew shortages", self.open_shortage_count, f"{self.open_shortage_count} open", "red"),
                ("Overdue HSSE actions", self.hsse_overdue_action_count, f"{self.hsse_overdue_action_count} overdue", "orange"),
            ]),
            _bar_chart("Safety workload", "HSSE", "Open safety exposure by control type.", [
                ("Open incidents", self.hsse_incident_count, f"{self.hsse_incident_count} incidents", "orange"),
                ("High risks", self.hsse_high_risk_count, f"{self.hsse_high_risk_count} risks", "red"),
                ("Permit exceptions", self.hsse_permit_exception_count, f"{self.hsse_permit_exception_count} permits", "amber"),
                ("Overdue actions", self.hsse_overdue_action_count, f"{self.hsse_overdue_action_count} actions", "purple"),
            ]),
        ]

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_visualization_html(self):
        builders = {
            "owner": "_owner_charts",
            "operations": "_operations_charts",
            "finance": "_finance_charts",
            "people": "_people_charts",
        }
        for dashboard in self:
            perspective = dashboard.dashboard_perspective or "owner"
            charts = getattr(dashboard, builders[perspective])()
            dashboard.visualization_html = Markup(
                '<div class="sedar_visual_grid">{}</div>'
            ).format(Markup("").join(charts))

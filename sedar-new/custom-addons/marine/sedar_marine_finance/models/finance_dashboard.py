from datetime import date

from odoo import _, api, models
from odoo.exceptions import AccessError


class SedarFinanceDashboard(models.AbstractModel):
    _name = "sedar.finance.dashboard"
    _description = "SEDAR Finance Operations Dashboard"

    @api.model
    def get_dashboard_data(self):
        self._check_dashboard_access()
        company = self.env.company
        today = date.today()
        moves = self.env["account.move"].search([
            ("company_id", "=", company.id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "!=", "cancel"),
        ])
        invoices = moves.filtered(lambda move: move.move_type == "out_invoice")
        posted = invoices.filtered(lambda move: move.state == "posted")
        open_invoices = posted.filtered(lambda move: move.amount_residual_signed > 0)
        overdue = open_invoices.filtered(
            lambda move: move.invoice_date_due and move.invoice_date_due < today
        )
        credits = moves.filtered(
            lambda move: move.move_type == "out_refund" and move.state == "posted"
        )
        service_orders = self.env["sedar.marine.service.order"].search([
            ("company_id", "=", company.id),
            ("billing_status", "in", ["review", "pricing_exception"]),
        ])
        aging = self._aging_summary(open_invoices, today)
        billed = sum(posted.mapped("amount_total_signed"))
        outstanding = sum(open_invoices.mapped("amount_residual_signed"))
        credit_total = abs(sum(credits.mapped("amount_total_signed")))
        return {
            "company": company.display_name,
            "currency": company.currency_id.name,
            "as_of": today.isoformat(),
            "summary": {
                "net_invoiced": billed - credit_total,
                "outstanding": outstanding,
                "overdue": sum(overdue.mapped("amount_residual_signed")),
                "applied": billed - outstanding,
            },
            "pipeline": {
                "billing_review": len(service_orders.filtered(
                    lambda order: order.billing_status == "review"
                )),
                "pricing_exception": len(service_orders.filtered(
                    lambda order: order.billing_status == "pricing_exception"
                )),
                "draft_invoice": len(invoices.filtered(
                    lambda move: move.state == "draft"
                )),
            },
            "receivables": {
                "open": len(open_invoices),
                "partial": len(posted.filtered(
                    lambda move: move.payment_state == "partial"
                )),
                "overdue": len(overdue),
                "paid": len(posted.filtered(
                    lambda move: move.payment_state == "paid"
                )),
                "credit_notes": len(credits),
            },
            "aging": aging,
            "work_queue": self._work_queue(service_orders, invoices, overdue),
            "actions": self._dashboard_actions(today),
        }

    def _check_dashboard_access(self):
        allowed = (
            self.env.user.has_group("sedar_marine_finance.group_billing_officer")
            or self.env.user.has_group("sedar_marine_finance.group_accounting_manager")
        )
        if not allowed:
            raise AccessError(_("You do not have access to the Finance Operations dashboard."))

    def _aging_summary(self, invoices, today):
        buckets = {
            "current": {"label": "Current", "count": 0, "amount": 0.0},
            "days_1_30": {"label": "1-30 days", "count": 0, "amount": 0.0},
            "days_31_60": {"label": "31-60 days", "count": 0, "amount": 0.0},
            "days_61_plus": {"label": "61+ days", "count": 0, "amount": 0.0},
        }
        for invoice in invoices:
            days = (today - invoice.invoice_date_due).days if invoice.invoice_date_due else 0
            if days <= 0:
                key = "current"
            elif days <= 30:
                key = "days_1_30"
            elif days <= 60:
                key = "days_31_60"
            else:
                key = "days_61_plus"
            buckets[key]["count"] += 1
            buckets[key]["amount"] += invoice.amount_residual_signed
        maximum = max((bucket["amount"] for bucket in buckets.values()), default=0)
        for bucket in buckets.values():
            bucket["percent"] = (bucket["amount"] / maximum * 100) if maximum else 0
        return list(buckets.values())

    def _work_queue(self, service_orders, invoices, overdue):
        items = []
        for order in service_orders.sorted(
            key=lambda record: (record.billing_status != "pricing_exception", record.id)
        ):
            exception = order.billing_status == "pricing_exception"
            items.append({
                "model": order._name,
                "res_id": order.id,
                "kind": "Pricing exception" if exception else "Billing review",
                "tone": "danger" if exception else "info",
                "title": order.display_name,
                "customer": order.client_id.display_name,
                "detail": order.service_type_id.display_name,
                "amount": order.total_billable_amount,
                "currency": order.confirmed_currency_id.name or self.env.company.currency_id.name,
            })
        for invoice in invoices.filtered(lambda move: move.state == "draft").sorted("invoice_date"):
            items.append(self._invoice_queue_item(invoice, "Draft invoice", "warning"))
        for invoice in overdue.sorted("invoice_date_due"):
            days = (date.today() - invoice.invoice_date_due).days
            item = self._invoice_queue_item(invoice, "Overdue invoice", "danger")
            item["detail"] = f"{days} days overdue"
            items.append(item)
        return items[:10]

    def _invoice_queue_item(self, invoice, kind, tone):
        return {
            "model": invoice._name,
            "res_id": invoice.id,
            "kind": kind,
            "tone": tone,
            "title": invoice.name if invoice.name and invoice.name != "/" else invoice.ref or "Draft invoice",
            "customer": invoice.partner_id.display_name,
            "detail": invoice.invoice_origin or invoice.ref or "Customer invoice",
            "amount": invoice.amount_residual_signed or invoice.amount_total_signed,
            "currency": invoice.company_currency_id.name,
        }

    def _dashboard_actions(self, today):
        company_domain = [("company_id", "=", self.env.company.id)]
        return {
            "billing_review": self._action(
                _("Billing Reviews"), "sedar.marine.service.order",
                company_domain + [("billing_status", "=", "review")],
            ),
            "pricing_exception": self._action(
                _("Pricing Exceptions"), "sedar.marine.service.order",
                company_domain + [("billing_status", "=", "pricing_exception")],
            ),
            "draft_invoice": self._action(
                _("Draft Customer Invoices"), "account.move",
                company_domain + [("move_type", "=", "out_invoice"), ("state", "=", "draft")],
            ),
            "open": self._action(
                _("Open Receivables"), "account.move",
                company_domain + [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                  ("amount_residual", ">", 0)],
            ),
            "partial": self._action(
                _("Partially Paid Invoices"), "account.move",
                company_domain + [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                  ("payment_state", "=", "partial")],
            ),
            "overdue": self._action(
                _("Overdue Invoices"), "account.move",
                company_domain + [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                  ("amount_residual", ">", 0), ("invoice_date_due", "<", today.isoformat())],
            ),
            "paid": self._action(
                _("Paid Invoices"), "account.move",
                company_domain + [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                  ("payment_state", "=", "paid")],
            ),
            "credit_notes": self._action(
                _("Customer Credit Notes"), "account.move",
                company_domain + [("move_type", "=", "out_refund"), ("state", "=", "posted")],
            ),
        }

    def _action(self, name, model, domain):
        return {"name": name, "res_model": model, "domain": domain}

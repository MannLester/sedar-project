from odoo import api, models


class SedarFinanceDashboard(models.AbstractModel):
    _name = "sedar.finance.dashboard"
    _description = "SEDAR Finance Dashboard Snapshot"

    @api.model
    def get_snapshot(self):
        company = self.env.company.sudo()
        currency_id = company.currency_id.id
        data = {
            "companies": [{
                "id": company.id,
                "name": company.name,
                "currency_id": [company.currency_id.id, company.currency_id.display_name] if company.currency_id else False,
            }],
            "petty": self._search_read(
                "sedar.finance.petty.cash",
                [("state", "=", "submitted")],
                ["name", "description", "amount", "date", "currency_id"],
                "date asc, id asc",
                6,
            ),
            "advances": self._search_read(
                "sedar.finance.cash.advance",
                [("state", "in", ["submitted", "released", "partial"])],
                ["name", "employee_id", "purpose", "amount", "outstanding_amount", "date", "state", "currency_id"],
                "date asc, id asc",
                40,
            ),
            "disbursements": self._search_read(
                "sedar.finance.disbursement",
                [("state", "in", ["submitted", "released"])],
                ["name", "supplier_id", "amount", "date", "state", "payment_type", "check_status", "currency_id"],
                "date desc, id desc",
                30,
            ),
            "collections": self._search_read(
                "sedar.finance.collection",
                [],
                ["name", "customer_id", "amount", "deposit_date", "state", "currency_id"],
                "deposit_date desc, id desc",
                8,
            ),
            "invoices": self._read_group(
                "account.move",
                [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "!=", "paid")],
                ["amount_residual_signed:sum"],
                [],
            ),
            "bills": self._read_group(
                "account.move",
                [("move_type", "=", "in_invoice"), ("state", "=", "posted"), ("payment_state", "!=", "paid")],
                ["amount_residual_signed:sum"],
                [],
            ),
            "banks": self._search_read(
                "account.journal",
                [("type", "in", ["bank", "cash"])],
                [
                    "name",
                    "code",
                    "type",
                    "currency_id",
                    "sedar_statement_balance",
                    "sedar_statement_date",
                    "sedar_posted_book_balance",
                    "sedar_outstanding_checks",
                    "sedar_available_cash",
                ],
                "type, code",
                100,
            ),
            "billings": self._search_read(
                "sedar.towage.billing",
                [],
                ["name", "customer_id", "amount", "write_date", "invoice_id", "currency_id"],
                "write_date desc, id desc",
                8,
            ),
            "petty_count": self._search_count("sedar.finance.petty.cash", [("state", "=", "submitted")]),
            "advance_count": self._search_count("sedar.finance.cash.advance", [("state", "=", "submitted")]),
            "disbursement_count": self._search_count("sedar.finance.disbursement", [("state", "=", "submitted")]),
        }
        currency_ids = {
            currency_id,
            *self._currency_ids(data["banks"]),
            *self._currency_ids(data["collections"]),
            *self._currency_ids(data["disbursements"]),
            *self._currency_ids(data["billings"]),
        }
        data["currencies"] = self.env["res.currency"].sudo().browse([cid for cid in currency_ids if cid]).read(
            ["name", "symbol", "position", "decimal_places"]
        )
        return data

    def _search_read(self, model, domain, fields, order=None, limit=None):
        return self.env[model].sudo().search_read(domain, fields, order=order, limit=limit)

    def _read_group(self, model, domain, fields, groupby):
        return self.env[model].sudo().read_group(domain, fields, groupby)

    def _search_count(self, model, domain):
        return self.env[model].sudo().search_count(domain)

    def _currency_ids(self, rows):
        ids = set()
        for row in rows:
            value = row.get("currency_id")
            if isinstance(value, (list, tuple)) and value:
                ids.add(value[0])
            elif value:
                ids.add(value)
        return ids

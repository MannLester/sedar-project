from collections import defaultdict

from odoo import api, models


class SedarAisPosition(models.Model):
    _inherit = "sedar.ais.position"

    @api.model
    def _inventory_summaries(self, tugboats):
        location_tugs = {}
        for tugboat in tugboats:
            if tugboat.stock_location_id:
                location_tugs[tugboat.stock_location_id.id] = (
                    tugboat.id,
                    "serviceable",
                )
            if tugboat.quarantine_location_id:
                location_tugs[tugboat.quarantine_location_id.id] = (
                    tugboat.id,
                    "defective",
                )
        grouped_items = defaultdict(dict)
        quants = self.env["stock.quant"].sudo().search([
            ("company_id", "=", self.env.company.id),
            ("location_id", "in", list(location_tugs)),
            ("quantity", ">", 0),
        ])
        for quant in quants:
            tugboat_id, condition = location_tugs[quant.location_id.id]
            key = (quant.product_id.id, condition)
            values = grouped_items[tugboat_id].setdefault(key, {
                "id": quant.product_id.id,
                "name": quant.product_id.display_name,
                "uom": quant.product_uom_id.display_name,
                "condition": condition,
                "quantity": 0.0,
                "reserved": 0.0,
                "available": 0.0,
            })
            values["quantity"] += quant.quantity
            values["reserved"] += quant.reserved_quantity
            values["available"] += quant.available_quantity
        shortages = defaultdict(list)
        demands = self.env["sedar.replenishment.demand"].sudo().search([
            ("company_id", "=", self.env.company.id),
            ("tugboat_id", "in", tugboats.ids),
            ("state", "=", "open"),
        ], order="tugboat_id, scope, required_date, id")
        for demand in demands:
            shortages[demand.tugboat_id.id].append({
                "id": demand.id,
                "product": demand.product_id.display_name,
                "quantity": demand.remaining_qty,
                "uom": demand.product_uom_id.display_name,
                "scope": demand.scope,
            })
        summaries = {}
        for tugboat in tugboats:
            items = sorted(
                grouped_items[tugboat.id].values(),
                key=lambda item: (item["condition"] != "serviceable", item["name"]),
            )
            tug_shortages = shortages[tugboat.id]
            if not tugboat.stock_location_id:
                status = "unconfigured"
                reason = "Onboard stock location is not configured."
            elif tug_shortages:
                status = "blocked"
                reason = "%s active shortage%s" % (
                    len(tug_shortages),
                    "" if len(tug_shortages) == 1 else "s",
                )
            else:
                status = "ready"
                reason = "Onboard stock has no active replenishment shortages."
            summaries[tugboat.id] = {
                "status": status,
                "status_label": {
                    "ready": "Stock ready",
                    "blocked": "Stock attention",
                    "unconfigured": "Not configured",
                }[status],
                "reason": reason,
                "items": items,
                "shortages": tug_shortages,
            }
        return summaries

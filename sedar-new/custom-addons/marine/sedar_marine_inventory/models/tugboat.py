from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SedarTugboat(models.Model):
    _inherit = "sedar.tugboat"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Tugboat Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        check_company=True,
        help="Internal Inventory location representing fuel, lubricant, and onboard stores assigned to this tugboat.",
    )
    quarantine_location_id = fields.Many2one(
        "stock.location",
        string="Tugboat Quarantine Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        check_company=True,
        help="Internal Inventory location for defective or quarantined stock physically held on this tugboat.",
    )
    serviceable_stock_item_count = fields.Integer(
        compute="_compute_onboard_stock_item_count"
    )
    defective_stock_item_count = fields.Integer(
        compute="_compute_onboard_stock_item_count"
    )
    onboard_stock_item_count = fields.Integer(compute="_compute_onboard_stock_item_count")
    inventory_readiness_status = fields.Selection(
        [("ready", "Ready"), ("blocked", "Blocked")],
        compute="_compute_inventory_readiness",
    )
    inventory_readiness_reason = fields.Char(compute="_compute_inventory_readiness")
    open_replenishment_demand_count = fields.Integer(
        compute="_compute_inventory_readiness"
    )

    @api.constrains("company_id", "stock_location_id", "quarantine_location_id")
    def _check_sedar_stock_location(self):
        for tugboat in self:
            location = tugboat.stock_location_id
            if location and (
                location.company_id != tugboat.company_id
                or location.sedar_location_role != "tug"
                or location.sedar_tugboat_id != tugboat
            ):
                raise ValidationError(
                    _(
                        "A tugboat stock location must be the tagged company location linked to that tugboat."
                    )
                )
            quarantine = tugboat.quarantine_location_id
            if quarantine and (
                quarantine.company_id != tugboat.company_id
                or quarantine.sedar_location_role != "tug_quarantine"
                or quarantine.sedar_tugboat_id != tugboat
                or quarantine.location_id != location
            ):
                raise ValidationError(
                    _(
                        "A tugboat quarantine location must be the tagged child location linked to that tugboat."
                    )
                )

    @api.depends("stock_location_id", "quarantine_location_id")
    def _compute_onboard_stock_item_count(self):
        Quant = self.env["stock.quant"]
        for tugboat in self:
            serviceable = Quant.search_count([
                ("location_id", "=", tugboat.stock_location_id.id),
                ("quantity", ">", 0),
            ]) if tugboat.stock_location_id else 0
            defective = Quant.search_count([
                ("location_id", "=", tugboat.quarantine_location_id.id),
                ("quantity", ">", 0),
            ]) if tugboat.quarantine_location_id else 0
            tugboat.serviceable_stock_item_count = serviceable
            tugboat.defective_stock_item_count = defective
            tugboat.onboard_stock_item_count = serviceable + defective

    def action_open_onboard_stock(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "%s Onboard Stock" % self.display_name,
            "res_model": "stock.quant",
            "view_mode": "list",
            "domain": [("location_id", "in", (
                self.stock_location_id | self.quarantine_location_id
            ).ids)],
            "context": {"search_default_internal_loc": 1},
            "target": "current",
        }

    def _compute_inventory_readiness(self):
        Demand = self.env["sedar.replenishment.demand"]
        for tugboat in self:
            demands = Demand.search([
                ("tugboat_id", "=", tugboat.id),
                ("scope", "=", "baseline"),
                ("state", "=", "open"),
            ])
            tugboat.open_replenishment_demand_count = len(demands)
            tugboat.inventory_readiness_status = "blocked" if demands else "ready"
            tugboat.inventory_readiness_reason = ", ".join(
                "%s: %g short" % (row.product_id.display_name, row.remaining_qty)
                for row in demands[:3]
            ) or "Baseline serviceable onboard stock is ready."

    def action_open_replenishment_demands(self):
        self.ensure_one()
        action = self.env.ref(
            "sedar_marine_inventory.action_replenishment_demands"
        ).read()[0]
        action["domain"] = [("tugboat_id", "=", self.id)]
        action["context"] = {"default_tugboat_id": self.id}
        return action

    def action_open_inventory_history(self):
        self.ensure_one()
        action = self.env.ref(
            "sedar_marine_inventory.action_tug_inventory_history"
        ).read()[0]
        action["domain"] = [("tugboat_id", "=", self.id)]
        return action

    def action_open_inventory_movements(self):
        self.ensure_one()
        action = self.env.ref(
            "sedar_marine_inventory.action_tug_inventory_movements"
        ).read()[0]
        action["domain"] = [
            "|", ("source_tugboat_id", "=", self.id),
            ("destination_tugboat_id", "=", self.id),
        ]
        return action

    def action_record_physical_count(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Record Physical Count"),
            "res_model": "sedar.inventory.physical.count.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_company_id": self.company_id.id,
                "default_target_location_id": self.stock_location_id.id,
            },
        }

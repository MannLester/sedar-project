from odoo import fields, models


class SedarInventoryDashboard(models.Model):
    _name = "sedar.inventory.dashboard"
    _description = "Inventory Exception Dashboard"
    _check_company_auto = True

    name = fields.Char(required=True, default="Inventory Dashboard")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade",
    )
    baseline_blocker_count = fields.Integer(compute="_compute_indicators")
    operation_blocker_count = fields.Integer(compute="_compute_indicators")
    open_demand_count = fields.Integer(compute="_compute_indicators")
    overdue_demand_count = fields.Integer(compute="_compute_indicators")
    draft_movement_count = fields.Integer(compute="_compute_indicators")
    defective_onboard_qty = fields.Float(compute="_compute_indicators")
    low_stock_item_count = fields.Integer(compute="_compute_indicators")
    incoming_purchase_order_count = fields.Integer(compute="_compute_indicators")
    recent_movement_count = fields.Integer(compute="_compute_indicators")

    def _compute_indicators(self):
        today = fields.Date.context_today(self)
        for dashboard in self:
            company_domain = [("company_id", "=", dashboard.company_id.id)]
            Demand = self.env["sedar.replenishment.demand"]
            open_demands = Demand.search(company_domain + [("state", "=", "open")])
            dashboard.baseline_blocker_count = len(
                open_demands.filtered(lambda row: row.scope == "baseline")
            )
            dashboard.operation_blocker_count = len(
                open_demands.filtered(lambda row: row.scope == "operation")
            )
            dashboard.open_demand_count = len(open_demands)
            dashboard.overdue_demand_count = len(open_demands.filtered(
                lambda row: row.required_date and row.required_date < today
            ))
            Movement = self.env["sedar.tug.inventory.movement"]
            dashboard.draft_movement_count = Movement.search_count(
                company_domain + [("state", "=", "draft")]
            )
            dashboard.recent_movement_count = Movement.search_count(
                company_domain + [("state", "in", ["done", "reversed"])]
            )
            defective_quants = self.env["stock.quant"].search([
                ("company_id", "=", dashboard.company_id.id),
                ("location_id.sedar_location_role", "=", "tug_quarantine"),
                ("quantity", ">", 0),
            ])
            dashboard.defective_onboard_qty = sum(defective_quants.mapped("quantity"))
            products = self.env["product.product"].search([
                ("sedar_inventory_item", "=", True),
                "|", ("company_id", "=", False),
                ("company_id", "=", dashboard.company_id.id),
            ])
            dashboard.low_stock_item_count = len(products.filtered(
                lambda product: product.sedar_stock_status in {"low_stock", "out_of_stock"}
            ))
            dashboard.incoming_purchase_order_count = dashboard._incoming_po_count()

    def _incoming_po_count(self):
        self.ensure_one()
        if "purchase.order" not in self.env.registry:
            return 0
        orders = self.env["purchase.order"].search([
            ("company_id", "=", self.company_id.id),
            ("state", "in", ["purchase", "done"]),
        ])
        return len(orders.filtered(lambda order: any(
            line.product_id.sedar_inventory_item
            and line.qty_received < line.product_qty
            for line in order.order_line
        )))

    def _open(self, xmlid, domain):
        self.ensure_one()
        action = self.env.ref(xmlid).read()[0]
        action["domain"] = domain
        return action

    def action_open_baseline_blockers(self):
        return self._open(
            "sedar_marine_inventory.action_replenishment_demands",
            [("company_id", "=", self.company_id.id),
             ("scope", "=", "baseline"), ("state", "=", "open")],
        )

    def action_open_operation_blockers(self):
        return self._open(
            "sedar_marine_inventory.action_replenishment_demands",
            [("company_id", "=", self.company_id.id),
             ("scope", "=", "operation"), ("state", "=", "open")],
        )

    def action_open_demands(self):
        return self._open(
            "sedar_marine_inventory.action_replenishment_demands",
            [("company_id", "=", self.company_id.id), ("state", "=", "open")],
        )

    def action_open_overdue_demands(self):
        return self._open(
            "sedar_marine_inventory.action_replenishment_demands",
            [("company_id", "=", self.company_id.id), ("state", "=", "open"),
             ("required_date", "<", fields.Date.context_today(self))],
        )

    def action_open_draft_movements(self):
        return self._open(
            "sedar_marine_inventory.action_tug_inventory_movements",
            [("company_id", "=", self.company_id.id), ("state", "=", "draft")],
        )

    def action_open_recent_movements(self):
        return self._open(
            "sedar_marine_inventory.action_tug_inventory_movements",
            [("company_id", "=", self.company_id.id),
             ("state", "in", ["done", "reversed"])],
        )

    def action_open_defective_stock(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Defective Onboard Stock",
            "res_model": "stock.quant",
            "view_mode": "list",
            "domain": [("company_id", "=", self.company_id.id),
                       ("location_id.sedar_location_role", "=", "tug_quarantine"),
                       ("quantity", ">", 0)],
        }

    def action_open_low_stock(self):
        action = self.env.ref("sedar_marine_inventory.action_inventory_check").read()[0]
        action["domain"] = [("sedar_inventory_item", "=", True),
                            ("sedar_stock_status", "in", ["low_stock", "out_of_stock"])]
        return action

    def action_open_incoming_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Incoming Purchase Orders",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id),
                       ("state", "in", ["purchase", "done"])],
        }

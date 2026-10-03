from odoo import api, fields, models
from odoo.exceptions import UserError


class SedarInventoryShortageResolveWizard(models.TransientModel):
    _name = "sedar.inventory.shortage.resolve.wizard"
    _description = "Resolve Inventory Shortage"
    _check_company_auto = True

    demand_id = fields.Many2one(
        "sedar.replenishment.demand", required=True, readonly=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="demand_id.company_id", readonly=True)
    tugboat_id = fields.Many2one(related="demand_id.tugboat_id", readonly=True)
    product_id = fields.Many2one(related="demand_id.product_id", readonly=True)
    product_uom_id = fields.Many2one(
        related="demand_id.product_uom_id", readonly=True
    )
    remaining_qty = fields.Float(related="demand_id.remaining_qty", readonly=True)
    resolution = fields.Selection(
        [("movement", "Move Available Stock"),
         ("procurement", "Create Purchase Request")],
        required=True, default="movement",
    )
    source_location_id = fields.Many2one(
        "stock.location", check_company=True,
        domain="[('company_id', '=', company_id), ('sedar_location_role', 'in', ['storage', 'tug'])]",
    )
    source_tugboat_id = fields.Many2one(
        related="source_location_id.sedar_tugboat_id", readonly=True
    )
    source_available_qty = fields.Float(compute="_compute_source_facts")
    incoming_purchase_qty = fields.Float(compute="_compute_source_facts")
    quantity = fields.Float(required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        demand = self.env["sedar.replenishment.demand"].browse(
            values.get("demand_id")
        ).exists()
        if demand:
            values.setdefault(
                "source_location_id",
                demand.company_id.sedar_default_storage_location_id.id,
            )
            values.setdefault("quantity", demand.remaining_qty)
        return values

    @api.depends("source_location_id", "product_id", "demand_id")
    def _compute_source_facts(self):
        Quant = self.env["stock.quant"]
        PurchaseLine = (
            self.env["purchase.order.line"]
            if "purchase.order.line" in self.env.registry else False
        )
        for wizard in self:
            wizard.source_available_qty = (
                Quant._get_available_quantity(
                    wizard.product_id, wizard.source_location_id, strict=True
                )
                if wizard.product_id and wizard.source_location_id else 0.0
            )
            wizard.incoming_purchase_qty = 0.0
            if PurchaseLine and wizard.product_id:
                lines = PurchaseLine.search([
                    ("product_id", "=", wizard.product_id.id),
                    ("order_id.company_id", "=", wizard.company_id.id),
                    ("order_id.state", "in", ["purchase", "done"]),
                ])
                wizard.incoming_purchase_qty = sum(
                    max(line.product_qty - line.qty_received, 0.0) for line in lines
                )

    def action_apply(self):
        self.ensure_one()
        if self.demand_id.state != "open":
            raise UserError("Only an open Replenishment Demand can be resolved.")
        if self.resolution == "procurement":
            return self.demand_id.action_create_purchase_request()
        if not self.source_location_id:
            raise UserError("Select a serviceable source location.")
        quantity = self.quantity
        if quantity <= 0:
            raise UserError("Movement quantity must be greater than zero.")
        movement = self.env["sedar.tug.inventory.movement"].create({
            "company_id": self.company_id.id,
            "action": "transfer",
            "product_id": self.product_id.id,
            "quantity": quantity,
            "source_location_id": self.source_location_id.id,
            "destination_location_id": self.tugboat_id.stock_location_id.id,
            "reason_code": "service_order_shortage",
            "demand_id": self.demand_id.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Inventory Movement",
            "res_model": movement._name,
            "res_id": movement.id,
            "view_mode": "form",
            "target": "current",
        }

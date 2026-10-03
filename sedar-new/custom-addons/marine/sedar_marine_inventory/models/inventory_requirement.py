from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarInventoryRequirement(models.Model):
    _name = "sedar.inventory.requirement"
    _description = "Service Order Inventory Requirement"
    _inherit = ["sedar.inventory.mixin"]
    _order = "order_id, product_id"
    _check_company_auto = True

    order_id = fields.Many2one(
        "sedar.marine.service.order",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id", store=True, index=True, readonly=True
    )
    tug_assignment_id = fields.Many2one(
        "sedar.tug.assignment", ondelete="cascade", index=True, check_company=True
    )
    tugboat_id = fields.Many2one(
        related="tug_assignment_id.tugboat_id", store=True, index=True, readonly=True
    )
    tug_location_id = fields.Many2one(
        related="tugboat_id.stock_location_id",
        string="Tug Stock Location",
        store=True,
        index=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    source_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        check_company=True,
    )
    expected_consumption_qty = fields.Float(required=True, default=1.0)
    minimum_reserve_qty = fields.Float(default=0.0)
    required_qty = fields.Float(compute="_compute_stock_status", store=True, string="Required Onboard")
    available_qty = fields.Float(compute="_compute_stock_status", store=True)
    warehouse_available_qty = fields.Float(compute="_compute_stock_status", store=True)
    transfer_required_qty = fields.Float(compute="_compute_stock_status", store=True)
    procurement_required_qty = fields.Float(compute="_compute_stock_status", store=True)
    shortage_qty = fields.Float(compute="_compute_stock_status", store=True)
    readiness_state = fields.Selection(
        [
            ("ready", "Onboard"),
            ("transfer_required", "Warehouse Transfer Required"),
            ("purchase_required", "Purchase Required"),
        ],
        compute="_compute_stock_status",
        store=True,
    )
    auto_generated = fields.Boolean(default=False)
    note = fields.Text()
    is_readiness_blocking = fields.Boolean(
        related="product_id.sedar_readiness_critical", store=True, readonly=True,
    )

    @api.depends(
        "product_id", "source_location_id", "tug_location_id",
        "expected_consumption_qty", "minimum_reserve_qty",
    )
    def _compute_stock_status(self):
        for line in self:
            required = line.expected_consumption_qty + line.minimum_reserve_qty
            line.required_qty = required
            warehouse = line._sedar_available_qty(line.product_id, line.source_location_id)
            onboard = (
                line._sedar_available_qty(line.product_id, line.tug_location_id)
                if line.tug_assignment_id and line.tug_location_id
                else warehouse if not line.tug_assignment_id else 0.0
            )
            shortage = max(required - onboard, 0.0)
            line.available_qty = onboard
            line.warehouse_available_qty = warehouse
            line.shortage_qty = shortage
            line.transfer_required_qty = min(shortage, warehouse) if line.tug_assignment_id else 0.0
            line.procurement_required_qty = (
                max(shortage - warehouse, 0.0) if line.tug_assignment_id else shortage
            )
            if shortage <= 0:
                line.readiness_state = "ready"
            elif line.tug_assignment_id and warehouse >= shortage:
                line.readiness_state = "transfer_required"
            else:
                line.readiness_state = "purchase_required"

    @api.constrains("expected_consumption_qty", "minimum_reserve_qty")
    def _check_required_qty(self):
        for line in self:
            if line.expected_consumption_qty <= 0:
                raise ValidationError("Expected consumption must be greater than zero.")
            if line.minimum_reserve_qty < 0:
                raise ValidationError("Minimum onboard reserve cannot be negative.")

    @api.constrains("order_id", "tug_assignment_id", "product_id", "source_location_id")
    def _check_requirement_company(self):
        for line in self:
            company = line.order_id.company_id
            if line.tug_assignment_id and line.tug_assignment_id.order_id != line.order_id:
                raise ValidationError("The tug assignment must belong to the Inventory Requirement Service Order.")
            for record in (line.product_id, line.source_location_id, line.tugboat_id, line.tug_location_id):
                if record.company_id and record.company_id != company:
                    raise ValidationError(
                        "Inventory Requirement products and locations must belong to the Service Order company."
                    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if self.env.context.get("sedar_inventory_generation"):
            return lines
        lines.mapped("order_id")._sync_inventory_readiness()
        lines.mapped("order_id").sync_automated_readiness()
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("sedar_inventory_generation"):
            return result
        if {
            "product_id", "source_location_id", "tug_assignment_id",
            "expected_consumption_qty", "minimum_reserve_qty",
        }.intersection(vals):
            self.mapped("order_id")._sync_inventory_readiness()
            self.mapped("order_id").sync_automated_readiness()
            self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return result

    def unlink(self):
        orders = self.mapped("order_id")
        result = super().unlink()
        if self.env.context.get("sedar_inventory_generation"):
            return result
        orders._sync_inventory_readiness()
        orders.sync_automated_readiness()
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return result

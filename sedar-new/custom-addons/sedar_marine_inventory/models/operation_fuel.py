from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarMarineOperation(models.Model):
    _inherit = "sedar.marine.operation"

    fuel_log_ids = fields.One2many("sedar.operation.fuel.log", "operation_id", string="Fuel and Lubricants")
    fuel_consumed_qty = fields.Float(compute="_compute_fuel_summary", store=True)

    @api.depends("fuel_log_ids.consumed_qty")
    def _compute_fuel_summary(self):
        for operation in self:
            operation.fuel_consumed_qty = sum(operation.fuel_log_ids.mapped("consumed_qty"))


class SedarOperationFuelLog(models.Model):
    _name = "sedar.operation.fuel.log"
    _description = "Marine Operation Fuel or Lubricant Log"
    _inherit = ["sedar.inventory.mixin"]
    _order = "operation_id, tugboat_id, product_id"

    operation_id = fields.Many2one("sedar.marine.operation", required=True, ondelete="cascade", index=True)
    tugboat_id = fields.Many2one("sedar.tugboat", required=True, ondelete="restrict")
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    source_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
    )
    tug_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
    )
    opening_qty = fields.Float(default=0.0)
    issued_qty = fields.Float(default=0.0)
    consumed_qty = fields.Float(default=0.0)
    stock_move_ids = fields.Many2many("stock.move", string="Inventory Movements", copy=False)
    remaining_qty = fields.Float(compute="_compute_remaining_qty", store=True)
    state = fields.Selection(
        [("draft", "Draft"), ("issued", "Issued"), ("consumed", "Consumption Recorded")],
        default="draft",
        required=True,
    )
    note = fields.Text()

    @api.depends("opening_qty", "issued_qty", "consumed_qty")
    def _compute_remaining_qty(self):
        for log in self:
            log.remaining_qty = log.opening_qty + log.issued_qty - log.consumed_qty

    @api.onchange("tugboat_id")
    def _onchange_tugboat_id(self):
        if self.tugboat_id.stock_location_id:
            self.tug_location_id = self.tugboat_id.stock_location_id

    @api.constrains("opening_qty", "issued_qty", "consumed_qty")
    def _check_quantities(self):
        for log in self:
            if min(log.opening_qty, log.issued_qty, log.consumed_qty) < 0:
                raise ValidationError("Fuel and lubricant quantities cannot be negative.")
            if log.consumed_qty > log.opening_qty + log.issued_qty:
                raise ValidationError("Consumed quantity cannot exceed opening plus issued quantity.")

    def _check_inventory_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_marine_inventory.group_marine_inventory_manager"):
            raise AccessError("Only a Marine Inventory Manager may issue or confirm fuel consumption.")

    def action_issue_to_tug(self):
        self._check_inventory_manager()
        for log in self:
            if log.state != "draft":
                raise UserError("Only draft fuel logs can be issued.")
            if not log.issued_qty:
                raise UserError("Enter issued quantity before issuing fuel or lubricant.")
            available = log._sedar_available_qty(log.product_id, log.source_location_id)
            if available < log.issued_qty:
                raise UserError("%s is short by %.2f." % (log.product_id.display_name, log.issued_qty - available))
            move = log._sedar_create_done_move(
                log.product_id, log.issued_qty, log.source_location_id,
                log.tug_location_id, "Fuel issue: %s" % log.operation_id.display_name,
            )
            log.write({"stock_move_ids": [(4, move.id)]})
            log.state = "issued"
        return True

    def action_record_consumption(self):
        self._check_inventory_manager()
        for log in self:
            if not log.consumed_qty:
                raise UserError("Enter consumed quantity before recording consumption.")
            if log.state == "draft":
                log.action_issue_to_tug()
            move = log._sedar_create_done_move(
                log.product_id, log.consumed_qty, log.tug_location_id,
                log.source_location_id, "Fuel consumption: %s" % log.operation_id.display_name,
            )
            log.write({"stock_move_ids": [(4, move.id)]})
            log.state = "consumed"
        return True

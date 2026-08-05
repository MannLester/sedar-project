from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    sedar_part_line_ids = fields.One2many(
        "sedar.maintenance.part.line",
        "maintenance_request_id",
        string="Spare Parts",
    )
    sedar_parts_status = fields.Selection(
        [
            ("none", "No Parts"),
            ("shortage", "Parts Shortage"),
            ("reserved", "Reserved"),
            ("issued", "Issued"),
            ("consumed", "Consumed"),
        ],
        compute="_compute_sedar_parts_status",
        store=True,
    )

    @api.depends("sedar_part_line_ids.state")
    def _compute_sedar_parts_status(self):
        order_rank = {"shortage": 1, "reserved": 2, "issued": 3, "consumed": 4}
        for request in self:
            states = request.sedar_part_line_ids.mapped("state")
            if not states:
                request.sedar_parts_status = "none"
            elif "shortage" in states:
                request.sedar_parts_status = "shortage"
            elif all(state == "consumed" for state in states):
                request.sedar_parts_status = "consumed"
            else:
                request.sedar_parts_status = max(states, key=lambda state: order_rank.get(state, 0))

    def _check_inventory_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sedar_marine_inventory.group_marine_inventory_manager"):
            raise AccessError("Only a Marine Inventory Manager may reserve, issue, or consume parts.")

    def action_sedar_reserve_parts(self):
        self._check_inventory_manager()
        self.mapped("sedar_part_line_ids").action_reserve()
        return True

    def action_sedar_issue_parts(self):
        self._check_inventory_manager()
        self.mapped("sedar_part_line_ids").action_issue()
        return True

    def action_sedar_consume_parts(self):
        self._check_inventory_manager()
        self.mapped("sedar_part_line_ids").action_consume()
        return True


class SedarMaintenancePartLine(models.Model):
    _name = "sedar.maintenance.part.line"
    _description = "Maintenance Spare Part Requirement"
    _inherit = ["sedar.inventory.mixin"]
    _order = "maintenance_request_id, product_id"

    maintenance_request_id = fields.Many2one("maintenance.request", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    source_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
    )
    requested_qty = fields.Float(required=True, default=1.0)
    available_qty = fields.Float(compute="_compute_state", store=True)
    reserved_qty = fields.Float(default=0.0)
    issued_qty = fields.Float(default=0.0)
    consumed_qty = fields.Float(default=0.0)
    shortage_qty = fields.Float(compute="_compute_state", store=True)
    state = fields.Selection(
        [("shortage", "Shortage"), ("reserved", "Reserved"), ("issued", "Issued"), ("consumed", "Consumed")],
        compute="_compute_state",
        store=True,
    )
    note = fields.Text()

    @api.depends("product_id", "source_location_id", "requested_qty", "reserved_qty", "issued_qty", "consumed_qty")
    def _compute_state(self):
        for line in self:
            line.available_qty = line._sedar_available_qty(line.product_id, line.source_location_id)
            if line.consumed_qty >= line.requested_qty:
                line.state = "consumed"
                line.shortage_qty = 0.0
            elif line.issued_qty >= line.requested_qty:
                line.state = "issued"
                line.shortage_qty = 0.0
            elif line.reserved_qty >= line.requested_qty:
                line.state = "reserved"
                line.shortage_qty = 0.0
            else:
                line.state = "shortage"
                line.shortage_qty = max(line.requested_qty - max(line.available_qty, line.reserved_qty), 0.0)

    @api.constrains("requested_qty", "reserved_qty", "issued_qty", "consumed_qty")
    def _check_quantities(self):
        for line in self:
            if line.requested_qty <= 0:
                raise ValidationError("Requested spare-part quantity must be greater than zero.")
            if min(line.reserved_qty, line.issued_qty, line.consumed_qty) < 0:
                raise ValidationError("Spare-part quantities cannot be negative.")
            if line.consumed_qty > line.issued_qty:
                raise ValidationError("Consumed quantity cannot exceed issued quantity.")
            if line.issued_qty > line.reserved_qty:
                raise ValidationError("Issued quantity cannot exceed reserved quantity.")

    def action_reserve(self):
        for line in self:
            if line.available_qty < line.requested_qty:
                raise UserError("%s is short by %.2f." % (line.product_id.display_name, line.shortage_qty))
            line.reserved_qty = line.requested_qty
        return True

    def action_issue(self):
        for line in self:
            if line.reserved_qty < line.requested_qty:
                line.action_reserve()
            line._sedar_adjust_stock(line.product_id, line.source_location_id, -line.requested_qty)
            line.write({"issued_qty": line.requested_qty})
        return True

    def action_consume(self):
        for line in self:
            if line.issued_qty < line.requested_qty:
                line.action_issue()
            line.write({"consumed_qty": line.requested_qty})
        return True

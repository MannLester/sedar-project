from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


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
                request.sedar_parts_status = max(
                    states, key=lambda state: order_rank.get(state, 0)
                )

    def action_sedar_reserve_parts(self):
        self.mapped("sedar_part_line_ids").action_reserve()
        return True

    def action_sedar_issue_parts(self):
        self.mapped("sedar_part_line_ids").action_issue()
        return True

    def action_sedar_consume_parts(self):
        self.mapped("sedar_part_line_ids").action_consume()
        return True


class SedarMaintenancePartLine(models.Model):
    _name = "sedar.maintenance.part.line"
    _description = "Maintenance Spare Part Requirement"
    _inherit = ["sedar.inventory.mixin"]
    _order = "maintenance_request_id, product_id"
    _check_company_auto = True

    maintenance_request_id = fields.Many2one(
        "maintenance.request", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="maintenance_request_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True
    )
    product_uom_id = fields.Many2one(
        related="product_id.uom_id", store=True, readonly=True
    )
    source_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        check_company=True,
    )
    requested_qty = fields.Float(required=True, default=1.0)
    available_qty = fields.Float(compute="_compute_state", store=True)
    reserved_qty = fields.Float(default=0.0)
    legacy_issued_qty = fields.Float(
        string="Legacy Issued Quantity", readonly=True, copy=False
    )
    legacy_consumed_qty = fields.Float(
        string="Legacy Consumed Quantity",
        readonly=True,
        copy=False,
    )
    issued_qty = fields.Float(compute="_compute_state", store=True, readonly=True)
    consumed_qty = fields.Float(compute="_compute_state", store=True, readonly=True)
    stock_move_ids = fields.Many2many(
        "stock.move", string="Inventory Movements", copy=False, check_company=True
    )
    lifecycle_ids = fields.Many2many(
        "sedar.inventory.lifecycle",
        "sedar_maintenance_part_lifecycle_rel",
        "part_line_id",
        "lifecycle_id",
        string="Inventory Lifecycles",
        readonly=True,
        copy=False,
        check_company=True,
    )
    shortage_qty = fields.Float(compute="_compute_state", store=True)
    state = fields.Selection(
        [
            ("shortage", "Shortage"),
            ("reserved", "Reserved"),
            ("issued", "Issued"),
            ("consumed", "Consumed"),
        ],
        compute="_compute_state",
        store=True,
    )
    note = fields.Text()

    def init(self):
        """Keep pre-lifecycle counters before stored computes replace their columns."""
        self.env.cr.execute(
            """
            UPDATE sedar_maintenance_part_line
               SET legacy_issued_qty = issued_qty
             WHERE legacy_issued_qty IS NULL
            """
        )
        self.env.cr.execute(
            """
            UPDATE sedar_maintenance_part_line
               SET legacy_consumed_qty = consumed_qty
             WHERE legacy_consumed_qty IS NULL
            """
        )

    @api.depends(
        "product_id",
        "source_location_id",
        "requested_qty",
        "reserved_qty",
        "legacy_issued_qty",
        "legacy_consumed_qty",
        "stock_move_ids.state",
        "stock_move_ids.quantity",
        "lifecycle_ids.initial_qty",
        "lifecycle_ids.event_ids.event_type",
        "lifecycle_ids.event_ids.quantity",
        "lifecycle_ids.event_ids.stock_move_id.state",
    )
    def _compute_state(self):
        for line in self:
            line.available_qty = line._sedar_available_qty(
                line.product_id, line.source_location_id
            )
            lifecycle_moves = line.lifecycle_ids.mapped(
                "issue_move_id"
            ) | line.lifecycle_ids.mapped("event_ids.stock_move_id")
            legacy_moves = line.stock_move_ids - lifecycle_moves
            legacy_issued = sum(
                move.quantity
                for move in legacy_moves
                if move.state == "done" and move.location_id == line.source_location_id
            )
            legacy_consumed = sum(
                move.quantity
                for move in legacy_moves
                if move.state == "done" and move.location_dest_id.usage == "inventory"
            )
            line.issued_qty = max(line.legacy_issued_qty, legacy_issued) + sum(
                line.lifecycle_ids.mapped("initial_qty")
            )
            lifecycle_consumed = sum(
                event.quantity
                for event in line.lifecycle_ids.mapped("event_ids")
                if event.event_type == "consume" and event.stock_move_id.state == "done"
            )
            line.consumed_qty = (
                max(line.legacy_consumed_qty, legacy_consumed) + lifecycle_consumed
            )
            rounding = line.product_uom_id.rounding or 0.01
            if (
                float_compare(
                    line.consumed_qty, line.requested_qty, precision_rounding=rounding
                )
                >= 0
            ):
                line.state = "consumed"
                line.shortage_qty = 0.0
            elif (
                float_compare(
                    line.issued_qty, line.requested_qty, precision_rounding=rounding
                )
                >= 0
            ):
                line.state = "issued"
                line.shortage_qty = 0.0
            elif (
                float_compare(
                    line.reserved_qty, line.requested_qty, precision_rounding=rounding
                )
                >= 0
            ):
                line.state = "reserved"
                line.shortage_qty = 0.0
            else:
                line.state = "shortage"
                line.shortage_qty = max(
                    line.requested_qty - max(line.available_qty, line.reserved_qty), 0.0
                )

    @api.constrains("requested_qty", "reserved_qty")
    def _check_quantities(self):
        for line in self:
            if line.requested_qty <= 0:
                raise ValidationError(
                    "Requested spare-part quantity must be greater than zero."
                )
            if line.reserved_qty < 0:
                raise ValidationError("Spare-part quantities cannot be negative.")

    @api.constrains("maintenance_request_id", "product_id", "source_location_id")
    def _check_company_contract(self):
        for line in self:
            if not line.company_id:
                raise ValidationError(
                    "A maintenance spare-part line requires a company."
                )
            if (
                line.product_id.company_id
                and line.product_id.company_id != line.company_id
            ):
                raise ValidationError(
                    "The spare-part Item Type must be shared or belong to the "
                    "work-order company."
                )
            if line.source_location_id.company_id != line.company_id:
                raise ValidationError(
                    "The spare-part Storage location must belong to the "
                    "work-order company."
                )

    def _check_exact_inventory_officer(self):
        for line in self:
            officer = line.company_id.sedar_procurement_inventory_officer_id
            if not officer or self.env.user != officer:
                raise AccessError(
                    "Only this company's configured Procurement and Inventory Officer "
                    "may reserve, issue, or consume parts."
                )

    def _lock_and_reload(self):
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM sedar_maintenance_part_line WHERE id IN %s FOR UPDATE",
            [tuple(self.ids)],
        )
        self.invalidate_recordset(
            ["reserved_qty", "issued_qty", "consumed_qty", "state", "lifecycle_ids"]
        )

    def action_reserve(self):
        self._check_exact_inventory_officer()
        for line in self:
            if line.available_qty < line.requested_qty:
                raise UserError(
                    "%s is short by %.2f."
                    % (line.product_id.display_name, line.shortage_qty)
                )
            line.reserved_qty = line.requested_qty
        return True

    def action_issue(self):
        self._check_exact_inventory_officer()
        for line in self:
            line._lock_and_reload()
            rounding = line.product_uom_id.rounding
            remaining = line.requested_qty - line.issued_qty
            if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
                raise UserError("The requested maintenance parts are already issued.")
            if (
                float_compare(
                    line.reserved_qty, line.requested_qty, precision_rounding=rounding
                )
                < 0
            ):
                line.action_reserve()
            work_order = line.maintenance_request_id.sudo()
            tugboat = work_order.sedar_tugboat_id
            if not tugboat:
                raise UserError(
                    "Set the affected tugboat before issuing maintenance parts."
                )
            issue = self.env["sedar.inventory.issue"]._issue_to_tug(
                line.product_id,
                tugboat,
                remaining,
                "Maintenance parts issue: %s" % work_order.display_name,
                line.source_location_id,
            )
            line.write(
                {
                    "stock_move_ids": [(4, issue.stock_move_id.id)],
                    "lifecycle_ids": [(4, issue.lifecycle_id.id)],
                }
            )
        return True

    def action_consume(self):
        self._check_exact_inventory_officer()
        for line in self:
            line._lock_and_reload()
            if float_is_zero(
                line.issued_qty, precision_rounding=line.product_uom_id.rounding
            ):
                raise UserError("Issue the maintenance parts before consuming them.")
            open_lifecycles = line.lifecycle_ids.filtered(
                lambda item: item.state == "open"
            )
            if not open_lifecycles:
                raise UserError(
                    "The issued maintenance parts are already consumed or closed."
                )
            work_order = line.maintenance_request_id.sudo()
            for lifecycle in open_lifecycles:
                quantity = lifecycle.open_qty
                lifecycle.action_consume(
                    quantity,
                    "Consumed by maintenance work order %s"
                    % work_order.display_name,
                )
                closing_move = lifecycle.event_ids.filtered(
                    lambda event: event.event_type == "consume"
                )[-1:].stock_move_id
                line.write({"stock_move_ids": [(4, closing_move.id)]})
        return True

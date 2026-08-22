from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SedarMarineOperation(models.Model):
    _inherit = "sedar.marine.operation"

    fuel_log_ids = fields.One2many(
        "sedar.operation.fuel.log", "operation_id", string="Fuel and Lubricants"
    )
    fuel_consumed_qty = fields.Float(compute="_compute_fuel_summary", store=True)

    @api.depends("fuel_log_ids.consumed_qty")
    def _compute_fuel_summary(self):
        for operation in self:
            operation.fuel_consumed_qty = sum(
                operation.fuel_log_ids.mapped("consumed_qty")
            )


class SedarOperationFuelLog(models.Model):
    _name = "sedar.operation.fuel.log"
    _description = "Marine Operation Fuel or Lubricant Log"
    _inherit = ["sedar.inventory.mixin"]
    _order = "operation_id, tugboat_id, product_id"
    _check_company_auto = True

    operation_id = fields.Many2one(
        "sedar.marine.operation",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="operation_id.company_id", store=True, index=True, readonly=True
    )
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, ondelete="restrict", check_company=True
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
    tug_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        check_company=True,
    )
    opening_qty = fields.Float(
        default=0.0,
        help=(
            "Legacy opening balance. New issues are tracked through Inventory "
            "Lifecycles."
        ),
    )
    quantity_to_issue = fields.Float(string="Quantity to Issue", default=0.0)
    quantity_to_consume = fields.Float(string="Quantity to Consume", default=0.0)
    legacy_issued_qty = fields.Float(
        string="Legacy Issued Quantity", readonly=True, copy=False
    )
    legacy_consumed_qty = fields.Float(
        string="Legacy Consumed Quantity",
        readonly=True,
        copy=False,
    )
    issued_qty = fields.Float(
        compute="_compute_lifecycle_quantities", store=True, readonly=True
    )
    consumed_qty = fields.Float(
        compute="_compute_lifecycle_quantities", store=True, readonly=True
    )
    stock_move_ids = fields.Many2many(
        "stock.move", string="Inventory Movements", copy=False, check_company=True
    )
    lifecycle_ids = fields.Many2many(
        "sedar.inventory.lifecycle",
        "sedar_operation_fuel_lifecycle_rel",
        "fuel_log_id",
        "lifecycle_id",
        string="Inventory Lifecycles",
        readonly=True,
        copy=False,
        check_company=True,
    )
    remaining_qty = fields.Float(compute="_compute_lifecycle_quantities", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("consumed", "Consumption Recorded"),
        ],
        compute="_compute_lifecycle_quantities",
        store=True,
        readonly=True,
    )
    note = fields.Text()

    def init(self):
        """Keep pre-lifecycle counters before stored computes replace their columns."""
        self.env.cr.execute(
            """
            UPDATE sedar_operation_fuel_log
               SET legacy_issued_qty = issued_qty
             WHERE legacy_issued_qty IS NULL
            """
        )
        self.env.cr.execute(
            """
            UPDATE sedar_operation_fuel_log
               SET legacy_consumed_qty = consumed_qty
             WHERE legacy_consumed_qty IS NULL
            """
        )

    @api.depends(
        "opening_qty",
        "legacy_issued_qty",
        "legacy_consumed_qty",
        "stock_move_ids.state",
        "stock_move_ids.quantity",
        "lifecycle_ids.initial_qty",
        "lifecycle_ids.open_qty",
        "lifecycle_ids.event_ids.event_type",
        "lifecycle_ids.event_ids.quantity",
        "lifecycle_ids.event_ids.stock_move_id.state",
    )
    def _compute_lifecycle_quantities(self):
        for log in self:
            lifecycle_moves = log.lifecycle_ids.mapped(
                "issue_move_id"
            ) | log.lifecycle_ids.mapped("event_ids.stock_move_id")
            legacy_moves = log.stock_move_ids - lifecycle_moves
            legacy_issued = sum(
                move.quantity
                for move in legacy_moves
                if move.state == "done" and move.location_dest_id == log.tug_location_id
            )
            legacy_consumed = sum(
                move.quantity
                for move in legacy_moves
                if move.state == "done" and move.location_id == log.tug_location_id
            )
            lifecycle_issued = sum(log.lifecycle_ids.mapped("initial_qty"))
            lifecycle_consumed = sum(
                event.quantity
                for event in log.lifecycle_ids.mapped("event_ids")
                if event.event_type == "consume" and event.stock_move_id.state == "done"
            )
            log.issued_qty = (
                max(log.legacy_issued_qty, legacy_issued) + lifecycle_issued
            )
            log.consumed_qty = (
                max(log.legacy_consumed_qty, legacy_consumed) + lifecycle_consumed
            )
            log.remaining_qty = max(
                log.opening_qty + log.issued_qty - log.consumed_qty, 0.0
            )
            if log.consumed_qty:
                log.state = "consumed"
            elif log.issued_qty:
                log.state = "issued"
            else:
                log.state = "draft"

    @api.onchange("tugboat_id")
    def _onchange_tugboat_id(self):
        if self.tugboat_id.stock_location_id:
            self.tug_location_id = self.tugboat_id.stock_location_id

    @api.constrains("opening_qty", "quantity_to_issue", "quantity_to_consume")
    def _check_quantities(self):
        for log in self:
            if min(log.opening_qty, log.quantity_to_issue, log.quantity_to_consume) < 0:
                raise ValidationError(
                    "Fuel and lubricant quantities cannot be negative."
                )

    @api.constrains(
        "operation_id",
        "tugboat_id",
        "product_id",
        "source_location_id",
        "tug_location_id",
    )
    def _check_fuel_company(self):
        for log in self:
            company = log.operation_id.company_id
            for record in (
                log.tugboat_id,
                log.product_id,
                log.source_location_id,
                log.tug_location_id,
            ):
                if record.company_id and record.company_id != company:
                    raise ValidationError(
                        "Fuel products, tugboats, and locations must belong to the "
                        "Marine Operation company."
                    )
            if log.tug_location_id != log.tugboat_id.stock_location_id:
                raise ValidationError(
                    "The fuel log must use the selected tugboat's stock location."
                )

    def _check_exact_inventory_officer(self):
        for log in self:
            officer = log.company_id.sedar_procurement_inventory_officer_id
            if not officer or self.env.user != officer:
                raise AccessError(
                    "Only this company's configured Procurement and Inventory Officer "
                    "may issue or consume fuel and lubricant."
                )

    def _lock_and_reload(self):
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM sedar_operation_fuel_log WHERE id IN %s FOR UPDATE",
            [tuple(self.ids)],
        )
        self.invalidate_recordset(
            ["issued_qty", "consumed_qty", "remaining_qty", "state", "lifecycle_ids"]
        )

    def action_issue_to_tug(self):
        self._check_exact_inventory_officer()
        for log in self:
            log._lock_and_reload()
            quantity = log.quantity_to_issue
            if (
                float_compare(
                    quantity, 0.0, precision_rounding=log.product_uom_id.rounding
                )
                <= 0
            ):
                raise UserError("Enter a positive quantity to issue.")
            issue = self.env["sedar.inventory.issue"]._issue_to_tug(
                log.product_id,
                log.tugboat_id,
                quantity,
                "Fuel issue: %s" % log.operation_id.display_name,
                log.source_location_id,
            )
            log.write(
                {
                    "stock_move_ids": [(4, issue.stock_move_id.id)],
                    "lifecycle_ids": [(4, issue.lifecycle_id.id)],
                    "quantity_to_issue": 0.0,
                }
            )
        return True

    def action_record_consumption(self):
        self._check_exact_inventory_officer()
        for log in self:
            log._lock_and_reload()
            quantity = log.quantity_to_consume
            rounding = log.product_uom_id.rounding
            if float_compare(quantity, 0.0, precision_rounding=rounding) <= 0:
                raise UserError("Enter a positive quantity to consume.")
            open_qty = sum(log.lifecycle_ids.mapped("open_qty"))
            if float_compare(quantity, open_qty, precision_rounding=rounding) > 0:
                raise UserError(
                    "Consumption cannot exceed the quantity held in linked "
                    "Inventory Lifecycles."
                )
            remaining = quantity
            for lifecycle in log.lifecycle_ids.filtered(
                lambda item: item.state == "open"
            ).sorted("issued_at"):
                if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
                    break
                consume_qty = min(remaining, lifecycle.open_qty)
                lifecycle.action_consume(
                    consume_qty,
                    "Consumed by Marine Operation %s" % log.operation_id.display_name,
                )
                closing_move = lifecycle.event_ids.filtered(
                    lambda event: event.event_type == "consume"
                )[-1:].stock_move_id
                log.write({"stock_move_ids": [(4, closing_move.id)]})
                remaining -= consume_qty
            log.write({"quantity_to_consume": 0.0})
        return True

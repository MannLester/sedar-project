from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SedarInventoryPhysicalCountWizard(models.TransientModel):
    _name = "sedar.inventory.physical.count.wizard"
    _description = "Record Inventory Physical Count"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    target_location_id = fields.Many2one(
        "stock.location", required=True, check_company=True,
        domain="[('company_id', '=', company_id), ('sedar_location_role', 'in', ['storage', 'tug'])]",
    )
    tugboat_id = fields.Many2one(
        related="target_location_id.sedar_tugboat_id", readonly=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, check_company=True,
        domain=[("sedar_inventory_item", "=", True)],
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    current_serviceable_qty = fields.Float(compute="_compute_current_quantities")
    current_defective_qty = fields.Float(compute="_compute_current_quantities")
    serviceable_count = fields.Float(required=True)
    defective_count = fields.Float(required=True)
    note = fields.Text()

    @api.depends("target_location_id", "product_id")
    def _compute_current_quantities(self):
        Quant = self.env["stock.quant"]
        for wizard in self:
            serviceable, defective = wizard._condition_locations()
            wizard.current_serviceable_qty = (
                Quant._get_available_quantity(
                    wizard.product_id, serviceable, strict=True
                ) if wizard.product_id and serviceable else 0.0
            )
            wizard.current_defective_qty = (
                Quant._get_available_quantity(
                    wizard.product_id, defective, strict=True
                ) if wizard.product_id and defective else 0.0
            )

    @api.onchange("target_location_id", "product_id")
    def _onchange_count_target(self):
        self.serviceable_count = self.current_serviceable_qty
        self.defective_count = self.current_defective_qty

    def _condition_locations(self):
        self.ensure_one()
        if not self.target_location_id:
            return self.env["stock.location"], self.env["stock.location"]
        if self.target_location_id.sedar_location_role == "tug":
            return (
                self.target_location_id,
                self.target_location_id.sedar_tugboat_id.quarantine_location_id,
            )
        return self.target_location_id, self.company_id.sedar_quarantine_location_id

    def action_apply(self):
        self.ensure_one()
        if self.product_id.tracking != "none":
            raise UserError(_(
                "Count lot- or serial-tracked items by their individual lot or serial in Odoo Inventory."
            ))
        for quantity in (self.serviceable_count, self.defective_count):
            if float_compare(
                quantity, 0.0, precision_rounding=self.product_uom_id.rounding
            ) < 0:
                raise UserError(_("Counted quantities cannot be negative."))
            if quantity:
                self.product_id._sedar_validate_inventory_quantity(quantity)
        adjustment = self.company_id.sedar_adjustment_location_id
        if not adjustment:
            raise UserError(_("Configure the SEDAR Inventory Adjustment location first."))
        serviceable, defective = self._condition_locations()
        self._apply_delta(serviceable, self.current_serviceable_qty, self.serviceable_count)
        self._apply_delta(defective, self.current_defective_qty, self.defective_count)
        return {"type": "ir.actions.act_window_close"}

    def _apply_delta(self, location, current, counted):
        rounding = self.product_uom_id.rounding
        comparison = float_compare(counted, current, precision_rounding=rounding)
        if not comparison:
            return
        delta = abs(counted - current)
        source = self.company_id.sedar_adjustment_location_id if comparison > 0 else location
        destination = location if comparison > 0 else self.company_id.sedar_adjustment_location_id
        movement = self.env["sedar.tug.inventory.movement"].create({
            "company_id": self.company_id.id,
            "action": "correct",
            "product_id": self.product_id.id,
            "quantity": delta,
            "source_location_id": source.id,
            "destination_location_id": destination.id,
            "reason_code": "inventory_correction",
            "note": self.note or _("Physical count adjustment."),
            "source_shortage_acknowledged": True,
            "count_before_qty": current,
            "counted_qty": counted,
        })
        movement.action_complete()

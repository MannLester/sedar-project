from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class SedarTugInventoryMovement(models.Model):
    _inherit = "sedar.tug.inventory.movement"

    source_condition = fields.Selection(
        [("serviceable", "Serviceable"), ("defective", "Defective")],
        compute="_compute_projection", readonly=True,
    )
    destination_condition = fields.Selection(
        [("serviceable", "Serviceable"), ("defective", "Defective")],
        compute="_compute_projection", readonly=True,
    )
    source_available_qty = fields.Float(compute="_compute_projection", readonly=True)
    projected_source_qty = fields.Float(compute="_compute_projection", readonly=True)
    projected_destination_qty = fields.Float(compute="_compute_projection", readonly=True)
    source_readiness_effect = fields.Char(compute="_compute_projection", readonly=True)
    destination_readiness_effect = fields.Char(
        compute="_compute_projection", readonly=True
    )
    source_will_be_blocked = fields.Boolean(compute="_compute_projection")
    source_shortage_acknowledged = fields.Boolean(
        string="Acknowledge Source Readiness Impact",
        help="Confirms that the movement may leave the source tug below its baseline.",
    )

    @api.depends(
        "product_id", "lot_id", "quantity", "source_location_id",
        "destination_location_id",
    )
    def _compute_projection(self):
        Quant = self.env["stock.quant"]
        for movement in self:
            source_condition = movement._condition(movement.source_location_id)
            destination_condition = movement._condition(
                movement.destination_location_id
            )
            source = 0.0
            destination = 0.0
            if movement.product_id and movement.source_location_id:
                source = Quant._get_available_quantity(
                    movement.product_id, movement.source_location_id,
                    lot_id=movement.lot_id, strict=True,
                )
            if movement.product_id and movement.destination_location_id:
                destination = Quant._get_available_quantity(
                    movement.product_id, movement.destination_location_id,
                    lot_id=movement.lot_id, strict=True,
                )
            movement.source_condition = source_condition
            movement.destination_condition = destination_condition
            movement.source_available_qty = source
            movement.projected_source_qty = source - movement.quantity
            movement.projected_destination_qty = destination + movement.quantity
            movement.source_readiness_effect = movement._projected_readiness(
                movement.source_tugboat_id
            )
            movement.destination_readiness_effect = movement._projected_readiness(
                movement.destination_tugboat_id
            )
            movement.source_will_be_blocked = bool(
                movement.source_readiness_effect
                and movement.source_readiness_effect.startswith("Blocked")
            )

    def _projected_readiness(self, tugboat):
        self.ensure_one()
        if not tugboat or not self.product_id.sedar_readiness_critical:
            return False
        requirement = self.env["sedar.tug.stock.requirement"]._effective_for_tug(
            tugboat
        ).filtered(lambda row: row.product_id == self.product_id)[:1]
        if not requirement:
            return "No baseline requirement"
        quantity = self.env["stock.quant"]._get_available_quantity(
            self.product_id, tugboat.stock_location_id,
            lot_id=self.lot_id, strict=True,
        )
        if self.source_location_id == tugboat.stock_location_id:
            quantity -= self.quantity
        if self.destination_location_id == tugboat.stock_location_id:
            quantity += self.quantity
        if float_compare(
            quantity, requirement.required_qty,
            precision_rounding=self.product_uom_id.rounding,
        ) >= 0:
            return "Ready after movement"
        return "Blocked after movement (%g short)" % (
            requirement.required_qty - quantity
        )

    @api.model
    def _condition(self, location):
        if location.sedar_location_role in {
            "storage_quarantine", "tug_quarantine"
        }:
            return "defective"
        if location.sedar_location_role in {"storage", "tug"}:
            return "serviceable"
        return False

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SedarTugInventoryHistory(models.Model):
    _name = "sedar.tug.inventory.history"
    _description = "Tug Inventory History"
    _order = "completed_at desc, id desc"
    _check_company_auto = True

    movement_id = fields.Many2one(
        "sedar.tug.inventory.movement", required=True, readonly=True,
        ondelete="restrict", check_company=True,
    )
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, readonly=True, ondelete="restrict",
        check_company=True, index=True,
    )
    perspective = fields.Selection(
        [("incoming", "Incoming"), ("outgoing", "Outgoing"),
         ("condition", "Condition Change"), ("correction", "Correction")],
        required=True, readonly=True,
    )
    event_text = fields.Char(required=True, readonly=True)
    product_id = fields.Many2one(related="movement_id.product_id", store=True)
    quantity = fields.Float(related="movement_id.quantity", store=True)
    product_uom_id = fields.Many2one(related="movement_id.product_uom_id", store=True)
    source_location_id = fields.Many2one(related="movement_id.source_location_id", store=True)
    destination_location_id = fields.Many2one(
        related="movement_id.destination_location_id", store=True
    )
    actor_id = fields.Many2one(related="movement_id.completed_by_id", store=True)
    completed_at = fields.Datetime(related="movement_id.completed_at", store=True)
    reason_label = fields.Char(related="movement_id.reason_label", store=True)
    note = fields.Text(related="movement_id.note", store=True)
    stock_move_id = fields.Many2one(related="movement_id.stock_move_id", store=True)
    count_before_qty = fields.Float(related="movement_id.count_before_qty", store=True)
    counted_qty = fields.Float(related="movement_id.counted_qty", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get("sedar_history_create")):
            raise AccessError(_("Tug Inventory History is created by completed movements."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("sedar_history_internal") and set(vals) <= {
            "perspective", "event_text"
        }:
            return super().write(vals)
        raise AccessError(_("Tug Inventory History is immutable."))

    def unlink(self):
        raise AccessError(_("Tug Inventory History cannot be deleted."))

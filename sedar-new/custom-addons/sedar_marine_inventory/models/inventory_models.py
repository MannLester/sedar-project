from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarInventoryTemplate(models.Model):
    _name = "sedar.inventory.template"
    _description = "Service Order Inventory Template"
    _order = "service_type_id, name"

    name = fields.Char(required=True)
    service_type_id = fields.Many2one("sedar.marine.service.type", required=True, ondelete="cascade")
    tug_class_id = fields.Many2one("sedar.tug.class", ondelete="set null")
    source_location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
    )
    line_ids = fields.One2many("sedar.inventory.template.line", "template_id")
    active = fields.Boolean(default=True)


class SedarInventoryTemplateLine(models.Model):
    _name = "sedar.inventory.template.line"
    _description = "Service Order Inventory Template Line"
    _order = "sequence, product_id"

    template_id = fields.Many2one("sedar.inventory.template", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    product_uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    required_qty = fields.Float(required=True, default=1.0)
    per_tug = fields.Boolean(default=True)

    @api.constrains("required_qty")
    def _check_required_qty(self):
        for line in self:
            if line.required_qty <= 0:
                raise ValidationError("Inventory template quantities must be greater than zero.")


class SedarInventoryMixin(models.AbstractModel):
    _name = "sedar.inventory.mixin"
    _description = "SEDAR Inventory Helper"

    def _sedar_available_qty(self, product, location):
        if not product or not location:
            return 0.0
        return self.env["stock.quant"]._get_available_quantity(product, location, strict=True)

    def _sedar_adjust_stock(self, product, location, quantity_delta):
        """Fixture-only stock seeding helper.

        Operational actions must use ``_sedar_create_done_move`` below.  This
        method remains for deterministic demo opening balances and is never
        called by issue/consume actions.
        """
        if not product or not location or not quantity_delta:
            return
        self.env["stock.quant"]._update_available_quantity(product, location, quantity_delta)

    def _sedar_create_done_move(self, product, quantity, source, destination, origin):
        """Create an auditable, completed internal stock movement."""
        if not product or quantity <= 0 or not source or not destination:
            return self.env["stock.move"]
        move = self.env["stock.move"].create({
            "origin": origin,
            "company_id": self.env.company.id,
            "product_id": product.id,
            "product_uom_qty": quantity,
            "product_uom": product.uom_id.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
        })
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.write({"quantity": quantity})
        move.picked = True
        move._action_done()
        move.invalidate_recordset(["state"])
        return move

    def _sedar_consumption_location(self):
        Location = self.env["stock.location"]
        location = Location.search([
            ("name", "=", "SEDAR Tug Issue Consumption"),
            ("company_id", "=", self.env.company.id),
            ("usage", "=", "inventory"),
        ], limit=1)
        if location:
            return location
        virtual_parent = Location.search([
            ("usage", "=", "view"),
            ("company_id", "in", [False, self.env.company.id]),
        ], order="company_id desc, id", limit=1)
        return Location.create({
            "name": "SEDAR Tug Issue Consumption",
            "usage": "inventory",
            "location_id": virtual_parent.id,
            "company_id": self.env.company.id,
        })

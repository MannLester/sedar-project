from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SedarTugStockRequirement(models.Model):
    _name = "sedar.tug.stock.requirement"
    _description = "Tug Stock Requirement"
    _order = "product_id, tugboat_id, tug_class_id"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True,
        domain=[("sedar_inventory_item", "=", True),
                ("sedar_readiness_critical", "=", True)],
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    tug_class_id = fields.Many2one("sedar.tug.class", ondelete="cascade")
    tugboat_id = fields.Many2one(
        "sedar.tugboat", ondelete="cascade", check_company=True,
    )
    required_qty = fields.Float(required=True, default=1.0)
    active = fields.Boolean(default=True)
    note = fields.Text()

    _class_product_unique = models.Constraint(
        "UNIQUE(company_id, product_id, tug_class_id)",
        "A Tug Class may have only one requirement for an Item Type.",
    )
    _tug_product_unique = models.Constraint(
        "UNIQUE(company_id, product_id, tugboat_id)",
        "A tugboat may have only one override for an Item Type.",
    )

    @api.constrains(
        "company_id", "product_id", "tug_class_id", "tugboat_id", "required_qty"
    )
    def _check_requirement(self):
        for requirement in self:
            if bool(requirement.tug_class_id) == bool(requirement.tugboat_id):
                raise ValidationError(
                    "Select either one Tug Class default or one tugboat override."
                )
            if not requirement.product_id.sedar_readiness_critical:
                raise ValidationError(
                    "Tug Stock Requirements require a Readiness-Critical Item Type."
                )
            if requirement.required_qty < 0:
                raise ValidationError("Required quantity cannot be negative.")
            requirement.product_id._sedar_validate_inventory_quantity(
                requirement.required_qty
            ) if requirement.required_qty else None
            if (
                requirement.tugboat_id
                and requirement.tugboat_id.company_id != requirement.company_id
            ):
                raise ValidationError("The tugboat and requirement company must match.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return result

    def unlink(self):
        result = super().unlink()
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return result

    @api.model
    def _effective_for_tug(self, tugboat):
        requirements = self.search([
            ("company_id", "=", tugboat.company_id.id),
            ("active", "=", True),
            "|", ("tugboat_id", "=", tugboat.id),
            ("tug_class_id", "=", tugboat.tug_class_id.id),
        ])
        effective = self.browse()
        for product in requirements.mapped("product_id"):
            override = requirements.filtered(
                lambda row: row.product_id == product and row.tugboat_id == tugboat
            )[:1]
            effective |= override or requirements.filtered(
                lambda row: row.product_id == product and not row.tugboat_id
            )[:1]
        return effective

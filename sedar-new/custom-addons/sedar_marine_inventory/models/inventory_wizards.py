from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SedarInventoryDispositionWizard(models.TransientModel):
    _name = "sedar.inventory.disposition.wizard"
    _description = "Record SEDAR Inventory Disposition"
    _check_company_auto = True

    lifecycle_id = fields.Many2one(
        "sedar.inventory.lifecycle",
        required=True,
        readonly=True,
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one(
        related="lifecycle_id.company_id", readonly=True
    )
    action = fields.Selection(
        [
            ("return", "Return to Storage"),
            ("consume", "Consume"),
            ("dispose", "Dispose"),
        ],
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related="lifecycle_id.product_id", readonly=True
    )
    tugboat_id = fields.Many2one(
        related="lifecycle_id.tugboat_id", readonly=True
    )
    open_qty = fields.Float(related="lifecycle_id.open_qty", readonly=True)
    quantity = fields.Float(required=True)
    product_uom_id = fields.Many2one(
        related="lifecycle_id.product_uom_id", readonly=True
    )
    reason = fields.Text(required=True)

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        lifecycle = self.env["sedar.inventory.lifecycle"].browse(
            values.get("lifecycle_id")
        ).exists()
        if lifecycle and "quantity" in field_names:
            values["quantity"] = lifecycle.open_qty
        return values

    def action_confirm(self):
        self.ensure_one()
        actions = {
            "return": self.lifecycle_id.action_return,
            "consume": self.lifecycle_id.action_consume,
            "dispose": self.lifecycle_id.action_dispose,
        }
        action = actions.get(self.action)
        if not action:
            raise UserError(_("Select a valid inventory disposition."))
        action(self.quantity, self.reason)
        return {"type": "ir.actions.act_window_close"}


class SedarInventoryTechnicalWizard(models.TransientModel):
    _name = "sedar.inventory.technical.wizard"
    _description = "Record SEDAR Inventory Technical Action"
    _check_company_auto = True

    lifecycle_id = fields.Many2one(
        "sedar.inventory.lifecycle",
        required=True,
        readonly=True,
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one(
        related="lifecycle_id.company_id", readonly=True
    )
    action = fields.Selection(
        [
            ("assign", "Assign"),
            ("install", "Install"),
            ("remove", "Remove"),
        ],
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related="lifecycle_id.product_id", readonly=True
    )
    tugboat_id = fields.Many2one(
        related="lifecycle_id.tugboat_id", readonly=True
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Related Equipment",
        check_company=True,
        domain="[('company_id', '=', company_id), ('sedar_tugboat_id', '=', tugboat_id)]",
        help="Optional for spare or consumable assignment. Replacement Equipment receives its identity during installation.",
    )

    def action_confirm(self):
        self.ensure_one()
        if self.action == "assign":
            self.lifecycle_id.action_assign(self.equipment_id)
        elif self.action == "install":
            self.lifecycle_id.action_install()
        elif self.action == "remove":
            self.lifecycle_id.action_remove()
        else:
            raise UserError(_("Select a valid technical inventory action."))
        return {"type": "ir.actions.act_window_close"}

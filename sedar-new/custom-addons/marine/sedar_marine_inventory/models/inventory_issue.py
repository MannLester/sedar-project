from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


class SedarInventoryIssue(models.Model):
    _name = "sedar.inventory.issue"
    _description = "SEDAR Inventory Issue to Tug"
    _inherit = ["sedar.inventory.mixin"]
    _order = "issued_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False)
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, index=True, copy=False
    )
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    manufacturer_part_number = fields.Char(
        related="product_id.sedar_manufacturer_part_number",
        string="Manufacturer Part Number",
        readonly=True,
    )
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    source_location_id = fields.Many2one(
        "stock.location", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    tug_location_id = fields.Many2one(
        "stock.location", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    quantity = fields.Float(required=True, readonly=True)
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    purpose = fields.Text(required=True, readonly=True)
    issued_by_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    issued_at = fields.Datetime(required=True, readonly=True)
    stock_move_id = fields.Many2one(
        "stock.move", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    lot_id = fields.Many2one(
        "stock.lot", string="Serial / Lot", readonly=True, copy=False,
        ondelete="restrict", check_company=True,
    )
    lifecycle_id = fields.Many2one(
        "sedar.inventory.lifecycle", readonly=True, copy=False,
        ondelete="restrict", check_company=True,
    )
    legacy_consumed = fields.Boolean(
        string="Legacy One-step Consumption", readonly=True, copy=False, default=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get("sedar_inventory_issue_create")):
            raise AccessError("Use Issue to Tug to create an inventory issue.")
        return super().create(vals_list)

    def write(self, vals):
        if (
            self.env.su
            and self.env.context.get("sedar_inventory_issue_link_lifecycle")
            and set(vals) == {"lifecycle_id"}
        ):
            return super().write(vals)
        raise AccessError("Completed inventory issues are immutable.")

    def unlink(self):
        raise AccessError("Completed inventory issues cannot be deleted.")

    @api.model
    def _issue_to_tug(
        self, product, tugboat, quantity, purpose, source_location=None, lot=None
    ):
        if not product.sedar_inventory_item:
            raise UserError("Select a SEDAR Inventory Item.")
        if quantity <= 0:
            raise UserError("Issue quantity must be greater than zero.")
        if not purpose or not purpose.strip():
            raise UserError("Enter the purpose of this issue.")
        if (
            product.sedar_compatibility_scope == "restricted"
            and tugboat not in product.sedar_compatible_tugboat_ids
        ):
            raise UserError("%s is not compatible with %s." % (product.display_name, tugboat.display_name))
        source_location = source_location or self.env.company.sedar_default_storage_location_id
        company = source_location.company_id if source_location else self.env.company
        self._check_issue_authority(company)
        tug_location = tugboat.stock_location_id
        self._validate_issue_locations(company, tugboat, source_location, tug_location)
        self._validate_issue_serial(product, quantity, lot)
        available = self.env["sedar.inventory.lifecycle"]._available_quantity(
            product, source_location, lot
        )
        if float_compare(
            quantity, available, precision_rounding=product.uom_id.rounding
        ) > 0:
            raise UserError("Only %.2f %s is available to issue." % (
                available, product.uom_id.display_name
            ))
        name = self.env["ir.sequence"].next_by_code("sedar.inventory.issue") or "New"
        move = self.env["sedar.inventory.lifecycle"]._create_done_stock_move(
            product,
            quantity,
            source_location,
            tug_location,
            "%s - Issue to %s" % (name, tugboat.display_name),
            company,
            lot,
        )
        product.invalidate_recordset([
            "sedar_on_hand_qty",
            "sedar_reserved_qty",
            "sedar_available_to_issue",
            "sedar_stock_status",
            "sedar_code_locked",
        ])
        issue = self.sudo().with_context(sedar_inventory_issue_create=True).create({
            "name": name,
            "company_id": company.id,
            "product_id": product.id,
            "tugboat_id": tugboat.id,
            "source_location_id": source_location.id,
            "tug_location_id": tug_location.id,
            "quantity": quantity,
            "purpose": purpose.strip(),
            "issued_by_id": self.env.user.id,
            "issued_at": fields.Datetime.now(),
            "stock_move_id": move.id,
            "lot_id": lot.id if lot else False,
        })
        lifecycle = self.env["sedar.inventory.lifecycle"].sudo().with_context(
            sedar_inventory_lifecycle_create=True
        ).create({
            "issue_id": issue.id,
            "company_id": company.id,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "tugboat_id": tugboat.id,
            "source_location_id": source_location.id,
            "tug_location_id": tug_location.id,
            "issue_move_id": move.id,
            "initial_qty": quantity,
            "lot_id": lot.id if lot else False,
            "issued_by_id": self.env.user.id,
            "issued_at": issue.issued_at,
        })
        issue.sudo().with_context(sedar_inventory_issue_link_lifecycle=True).write({
            "lifecycle_id": lifecycle.id
        })
        return issue

    def _check_issue_authority(self, company):
        if not company or self.env.user != company.sedar_procurement_inventory_officer_id:
            raise AccessError(
                "Only this company's configured Procurement and Inventory Officer may issue stock."
            )

    def _validate_issue_locations(self, company, tugboat, source, destination):
        if not source or source.company_id != company or source.sedar_location_role != "storage":
            raise UserError("Issue stock from a company-owned tagged Storage location.")
        tug_company = getattr(tugboat, "company_id", False)
        if tug_company and tug_company != company:
            raise UserError("The tugboat belongs to another company.")
        if (
            not destination
            or destination.company_id != company
            or destination.sedar_location_role != "tug"
            or destination.sedar_tugboat_id != tugboat
        ):
            raise UserError("Configure this tugboat's tagged company stock location first.")

    def _validate_issue_serial(self, product, quantity, lot):
        if product.sedar_item_type != "replacement_equipment":
            if lot and lot.product_id != product:
                raise UserError("The selected lot or serial belongs to another Item Type.")
            return
        if product.tracking != "serial" or not lot or lot.product_id != product:
            raise UserError("Replacement Equipment requires its matching serial number.")
        if float_compare(
            quantity, 1.0, precision_rounding=product.uom_id.rounding
        ) != 0:
            raise UserError("Replacement Equipment must be issued one serialized unit at a time.")


class SedarInventoryIssueWizard(models.TransientModel):
    _name = "sedar.inventory.issue.wizard"
    _description = "Issue SEDAR Inventory to Tug"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain=[("sedar_inventory_item", "=", True)],
    )
    manufacturer_part_number = fields.Char(
        related="product_id.sedar_manufacturer_part_number",
        string="Manufacturer Part Number",
        readonly=True,
    )
    item_type = fields.Selection(
        related="product_id.sedar_item_type", string="Item Type", readonly=True
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('sedar_location_role', '=', 'storage'), ('usage', '=', 'internal')]",
        default=lambda self: self.env.company.sedar_default_storage_location_id,
    )
    available_to_issue = fields.Float(
        compute="_compute_available_to_issue",
        string="Available to Issue",
        readonly=True,
    )
    tugboat_id = fields.Many2one(
        "sedar.tugboat",
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    tug_location_id = fields.Many2one(
        related="tugboat_id.stock_location_id",
        string="Tugboat Stock Location",
        readonly=True,
    )
    quantity = fields.Float(required=True, default=1.0)
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    purpose = fields.Text(required=True)
    lot_id = fields.Many2one(
        "stock.lot",
        string="Serial / Lot",
        domain="[('product_id', '=', product_id)]",
        check_company=True,
    )

    @api.depends("product_id", "source_location_id", "lot_id")
    def _compute_available_to_issue(self):
        Lifecycle = self.env["sedar.inventory.lifecycle"]
        for wizard in self:
            wizard.available_to_issue = Lifecycle._available_quantity(
                wizard.product_id, wizard.source_location_id, wizard.lot_id
            ) if wizard.product_id and wizard.source_location_id else 0.0

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.lot_id and self.lot_id.product_id != self.product_id:
            self.lot_id = False

    def action_issue(self):
        self.ensure_one()
        issue = self.env["sedar.inventory.issue"]._issue_to_tug(
            self.product_id,
            self.tugboat_id,
            self.quantity,
            self.purpose,
            self.source_location_id,
            self.lot_id,
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Inventory Issue",
            "res_model": "sedar.inventory.issue",
            "res_id": issue.id,
            "view_mode": "form",
            "target": "current",
        }

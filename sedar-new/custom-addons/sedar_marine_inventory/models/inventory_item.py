from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ProductProduct(models.Model):
    _inherit = "product.product"

    sedar_inventory_item = fields.Boolean(
        string="SEDAR Inventory Item",
        index=True,
        help="Includes this stock-backed Item Type in the SEDAR Inventory Check workspace.",
    )
    sedar_manufacturer_part_number = fields.Char(
        string="Manufacturer Part Number",
        index=True,
    )
    sedar_item_type = fields.Selection(
        [
            ("fuel_lubricant", "Fuel / Lubricant"),
            ("spare_consumable", "Spare / Consumable"),
            ("replacement_equipment", "Replacement Equipment"),
        ],
        string="Item Type",
        required=True,
        default="spare_consumable",
        index=True,
    )
    sedar_compatibility_scope = fields.Selection(
        [("fleet", "Fleet-wide"), ("restricted", "Selected Tugboats")],
        string="Tug Compatibility",
        default="fleet",
        required=True,
    )
    sedar_compatible_tugboat_ids = fields.Many2many(
        "sedar.tugboat",
        "sedar_inventory_product_tugboat_rel",
        "product_id",
        "tugboat_id",
        string="Compatible Tugboats",
    )
    sedar_reorder_point = fields.Float(
        string="Reorder Point",
        default=0.0,
    )
    sedar_stock_location_id = fields.Many2one(
        "stock.location",
        string="Warehouse Location",
        compute="_compute_sedar_inventory_check",
    )
    sedar_on_hand_qty = fields.Float(
        string="On Hand",
        compute="_compute_sedar_inventory_check",
    )
    sedar_reserved_qty = fields.Float(
        string="Reserved",
        compute="_compute_sedar_inventory_check",
    )
    sedar_available_to_issue = fields.Float(
        string="Available to Issue",
        compute="_compute_sedar_inventory_check",
    )
    sedar_stock_status = fields.Selection(
        [("in_stock", "In Stock"), ("low_stock", "Low Stock"), ("out_of_stock", "Out of Stock")],
        string="Stock Status",
        compute="_compute_sedar_inventory_check",
        search="_search_sedar_stock_status",
    )
    sedar_compatibility_display = fields.Char(
        string="Compatibility",
        compute="_compute_sedar_compatibility_display",
    )
    sedar_code_locked = fields.Boolean(
        string="SEDAR Item Code Locked",
        compute="_compute_sedar_code_locked",
    )

    @api.depends_context("company")
    @api.depends("sedar_reorder_point")
    def _compute_sedar_inventory_check(self):
        company_locations = {}
        Quant = self.env["stock.quant"]
        for product in self:
            company = product.company_id or self.env.company
            locations = company_locations.get(company.id)
            if locations is None:
                locations = self.env["stock.location"].search(
                    [
                        ("company_id", "=", company.id),
                        ("sedar_location_role", "=", "storage"),
                        ("usage", "=", "internal"),
                    ]
                )
                company_locations[company.id] = locations
            location = company.sedar_default_storage_location_id
            product.sedar_stock_location_id = location
            quants = Quant.search([
                ("product_id", "=", product.id),
                ("location_id", "in", locations.ids),
            ]) if locations else Quant
            on_hand = sum(quants.mapped("quantity")) if locations else 0.0
            reserved = sum(quants.mapped("reserved_quantity")) if locations else 0.0
            available = on_hand - reserved
            product.sedar_on_hand_qty = on_hand
            product.sedar_reserved_qty = reserved
            product.sedar_available_to_issue = available
            if available <= 0:
                product.sedar_stock_status = "out_of_stock"
            elif product.sedar_reorder_point and available <= product.sedar_reorder_point:
                product.sedar_stock_status = "low_stock"
            else:
                product.sedar_stock_status = "in_stock"

    @api.model
    def _search_sedar_stock_status(self, operator, value):
        if operator not in {"=", "!=", "in", "not in"}:
            raise UserError("Stock Status supports exact-match filters only.")
        requested = set(value if isinstance(value, (list, tuple)) else [value])
        products = self.search([("sedar_inventory_item", "=", True)])
        matched = products.filtered(lambda product: product.sedar_stock_status in requested)
        positive = operator in {"=", "in"}
        return [("id", "in" if positive else "not in", matched.ids)]

    @api.depends("sedar_compatibility_scope", "sedar_compatible_tugboat_ids.name")
    def _compute_sedar_compatibility_display(self):
        for product in self:
            product.sedar_compatibility_display = (
                "Fleet-wide"
                if product.sedar_compatibility_scope == "fleet"
                else ", ".join(product.sedar_compatible_tugboat_ids.mapped("name"))
            )

    def _compute_sedar_code_locked(self):
        Move = self.env["stock.move"]
        for product in self:
            product.sedar_code_locked = bool(product.id and Move.search_count([
                ("product_id", "=", product.id),
                ("state", "!=", "cancel"),
            ], limit=1))

    @api.constrains(
        "sedar_inventory_item",
        "default_code",
        "is_storable",
        "sedar_compatibility_scope",
        "sedar_compatible_tugboat_ids",
        "sedar_reorder_point",
        "sedar_item_type",
        "tracking",
    )
    def _check_sedar_inventory_item(self):
        for product in self:
            if not product.sedar_inventory_item:
                continue
            if not product.default_code:
                raise ValidationError("A SEDAR Inventory Item requires a SEDAR Item Code.")
            if not product.is_storable:
                raise ValidationError("A SEDAR Inventory Item must track inventory.")
            if (
                product.sedar_item_type == "replacement_equipment"
                and product.tracking != "serial"
            ):
                raise ValidationError(
                    "Replacement Equipment must use Odoo serial-number tracking."
                )
            duplicate = self.search_count([
                ("id", "!=", product.id),
                ("sedar_inventory_item", "=", True),
                ("default_code", "=ilike", product.default_code),
            ], limit=1)
            if duplicate:
                raise ValidationError("SEDAR Item Code must be unique.")
            if product.sedar_compatibility_scope == "restricted" and not product.sedar_compatible_tugboat_ids:
                raise ValidationError("Select at least one compatible tugboat for a restricted Item Type.")
            if product.sedar_reorder_point < 0:
                raise ValidationError("Reorder Point cannot be negative.")

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("sedar_compatibility_scope") == "fleet":
                vals["sedar_compatible_tugboat_ids"] = [Command.clear()]
            normalized.append(vals)
        return super().create(normalized)

    def write(self, vals):
        if {"default_code", "sedar_item_type"}.intersection(vals):
            for product in self.filtered("sedar_inventory_item"):
                if not product.sedar_code_locked:
                    continue
                if "default_code" in vals and vals["default_code"] != product.default_code:
                    raise UserError("The SEDAR Item Code cannot change after the first stock transaction.")
                if "sedar_item_type" in vals and vals["sedar_item_type"] != product.sedar_item_type:
                    raise UserError("Item Type cannot change after the first stock transaction.")
        vals = dict(vals)
        if vals.get("sedar_compatibility_scope") == "fleet":
            vals["sedar_compatible_tugboat_ids"] = [Command.clear()]
        return super().write(vals)

    def action_open_sedar_issue_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group("sedar_marine_inventory.group_marine_inventory_manager"):
            raise AccessError("Only a Procurement and Inventory Officer may issue stock to a tugboat.")
        return {
            "type": "ir.actions.act_window",
            "name": "Issue to Tug",
            "res_model": "sedar.inventory.issue.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_product_id": self.id},
        }


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
        "sedar.inventory.lifecycle", readonly=True, copy=False, ondelete="restrict"
    )
    legacy_consumed = fields.Boolean(
        string="Legacy One-step Consumption", readonly=True, copy=False, default=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sedar_inventory_issue_create"):
            raise AccessError("Use Issue to Tug to create an inventory issue.")
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("sedar_inventory_issue_link_lifecycle") and set(vals) == {"lifecycle_id"}:
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
        if quantity > available:
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
        issue = self.with_context(sedar_inventory_issue_create=True).create({
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
    source_location_id = fields.Many2one(
        related="product_id.sedar_stock_location_id",
        string="Warehouse Location",
        readonly=True,
    )
    available_to_issue = fields.Float(
        related="product_id.sedar_available_to_issue",
        string="Available to Issue",
        readonly=True,
    )
    tugboat_id = fields.Many2one("sedar.tugboat", required=True)
    quantity = fields.Float(required=True, default=1.0)
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    purpose = fields.Text(required=True)
    lot_id = fields.Many2one(
        "stock.lot",
        string="Serial / Lot",
        domain="[('product_id', '=', product_id)]",
    )

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

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


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

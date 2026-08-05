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
        warehouses = {}
        Quant = self.env["stock.quant"]
        for product in self:
            company = product.company_id or self.env.company
            warehouse = warehouses.get(company.id)
            if warehouse is None:
                warehouse = self.env["stock.warehouse"].search(
                    [("company_id", "=", company.id)], order="id", limit=1
                )
                warehouses[company.id] = warehouse
            location = warehouse.lot_stock_id
            product.sedar_stock_location_id = location
            quants = Quant.search([
                ("product_id", "=", product.id),
                ("location_id", "=", location.id),
            ]) if location else Quant
            on_hand = sum(quants.mapped("quantity")) if location else 0.0
            reserved = sum(quants.mapped("reserved_quantity")) if location else 0.0
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
    )
    def _check_sedar_inventory_item(self):
        for product in self:
            if not product.sedar_inventory_item:
                continue
            if not product.default_code:
                raise ValidationError("A SEDAR Inventory Item requires a SEDAR Item Code.")
            if not product.is_storable:
                raise ValidationError("A SEDAR Inventory Item must track inventory.")
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
        if "default_code" in vals:
            for product in self.filtered("sedar_inventory_item"):
                if product.sedar_code_locked and vals["default_code"] != product.default_code:
                    raise UserError("The SEDAR Item Code cannot change after the first stock transaction.")
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

    name = fields.Char(required=True, readonly=True, copy=False)
    product_id = fields.Many2one("product.product", required=True, readonly=True, ondelete="restrict")
    manufacturer_part_number = fields.Char(
        related="product_id.sedar_manufacturer_part_number",
        string="Manufacturer Part Number",
        readonly=True,
    )
    tugboat_id = fields.Many2one("sedar.tugboat", required=True, readonly=True, ondelete="restrict")
    source_location_id = fields.Many2one("stock.location", required=True, readonly=True, ondelete="restrict")
    quantity = fields.Float(required=True, readonly=True)
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    purpose = fields.Text(required=True, readonly=True)
    issued_by_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    issued_at = fields.Datetime(required=True, readonly=True)
    stock_move_id = fields.Many2one("stock.move", required=True, readonly=True, ondelete="restrict")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sedar_inventory_issue_create"):
            raise AccessError("Use Issue to Tug to create an inventory issue.")
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError("Completed inventory issues are immutable.")

    def unlink(self):
        raise AccessError("Completed inventory issues cannot be deleted.")

    @api.model
    def _issue_to_tug(self, product, tugboat, quantity, purpose, source_location=None):
        if not self.env.su and not self.env.user.has_group(
            "sedar_marine_inventory.group_marine_inventory_manager"
        ):
            raise AccessError("Only a Procurement and Inventory Officer may issue stock to a tugboat.")
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
        source_location = source_location or product.sedar_stock_location_id
        available = self._sedar_available_qty(product, source_location)
        if quantity > available:
            raise UserError("Only %.2f %s is available to issue." % (
                available, product.uom_id.display_name
            ))
        name = self.env["ir.sequence"].next_by_code("sedar.inventory.issue") or "New"
        destination = self._sedar_consumption_location()
        move = self._sedar_create_done_move(
            product,
            quantity,
            source_location,
            destination,
            "%s - Issue to %s" % (name, tugboat.display_name),
        )
        product.invalidate_recordset([
            "sedar_on_hand_qty",
            "sedar_reserved_qty",
            "sedar_available_to_issue",
            "sedar_stock_status",
            "sedar_code_locked",
        ])
        # TODO(next inventory iteration): decide Return to Warehouse and correction rules.
        return self.with_context(sedar_inventory_issue_create=True).create({
            "name": name,
            "product_id": product.id,
            "tugboat_id": tugboat.id,
            "source_location_id": source_location.id,
            "quantity": quantity,
            "purpose": purpose.strip(),
            "issued_by_id": self.env.user.id,
            "issued_at": fields.Datetime.now(),
            "stock_move_id": move.id,
        })


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

    def action_issue(self):
        self.ensure_one()
        issue = self.env["sedar.inventory.issue"]._issue_to_tug(
            self.product_id,
            self.tugboat_id,
            self.quantity,
            self.purpose,
            self.source_location_id,
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Inventory Issue",
            "res_model": "sedar.inventory.issue",
            "res_id": issue.id,
            "view_mode": "form",
            "target": "current",
        }

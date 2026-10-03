from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

MOVEMENT_REASONS = [
    ("routine_replenishment", "Routine replenishment"),
    ("service_order_shortage", "Service Order readiness shortage"),
    ("maintenance_requirement", "Maintenance requirement"),
    ("operational_reallocation", "Operational reallocation between tugboats"),
    ("defect_quarantine", "Defect or quarantine"),
    ("return_service", "Return to service after repair or inspection"),
    ("return_warehouse", "Return to warehouse"),
    ("consumption", "Consumption"),
    ("disposal", "Disposal"),
    ("inventory_correction", "Inventory correction"),
    ("other", "Other"),
]


class SedarTugInventoryMovement(models.Model):
    _name = "sedar.tug.inventory.movement"
    _description = "Tug Inventory Movement"
    _inherit = ["sedar.inventory.mixin"]
    _order = "completed_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default="New")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True, copy=False,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Completed"), ("reversed", "Reversed")],
        required=True, default="draft", readonly=True, copy=False, index=True,
    )
    action = fields.Selection(
        [
            ("transfer", "Transfer"),
            ("return", "Return"),
            ("consume", "Consume"),
            ("dispose", "Dispose"),
            ("mark_defective", "Mark Defective"),
            ("return_service", "Return to Service"),
            ("issue_maintenance", "Issue to Maintenance"),
            ("install", "Install"),
            ("remove", "Remove"),
            ("correct", "Inventory Correction"),
        ],
        required=True, default="transfer",
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True,
        domain=[("sedar_inventory_item", "=", True)],
    )
    quantity = fields.Float(required=True, default=1.0)
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    lot_id = fields.Many2one(
        "stock.lot", string="Serial / Lot", ondelete="restrict", check_company=True,
        domain="[('product_id', '=', product_id)]",
    )
    source_location_id = fields.Many2one(
        "stock.location", required=True, ondelete="restrict", check_company=True,
    )
    destination_location_id = fields.Many2one(
        "stock.location", required=True, ondelete="restrict", check_company=True,
    )
    source_tugboat_id = fields.Many2one(
        related="source_location_id.sedar_tugboat_id", store=True, readonly=True,
    )
    destination_tugboat_id = fields.Many2one(
        related="destination_location_id.sedar_tugboat_id", store=True, readonly=True,
    )
    count_before_qty = fields.Float(copy=False)
    counted_qty = fields.Float(copy=False)
    reason_code = fields.Selection(MOVEMENT_REASONS, required=True)
    reason_label = fields.Char(readonly=True, copy=False)
    note = fields.Text()
    evidence = fields.Binary(attachment=True)
    evidence_filename = fields.Char()
    stock_move_id = fields.Many2one(
        "stock.move", readonly=True, copy=False, ondelete="restrict", check_company=True,
    )
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    reversal_of_id = fields.Many2one(
        "sedar.tug.inventory.movement", readonly=True, copy=False, ondelete="restrict",
    )
    reversal_id = fields.Many2one(
        "sedar.tug.inventory.movement", readonly=True, copy=False, ondelete="restrict",
    )
    demand_id = fields.Many2one(
        "sedar.replenishment.demand", ondelete="set null", check_company=True,
    )
    history_ids = fields.One2many(
        "sedar.tug.inventory.history", "movement_id", readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_authority()
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "sedar.tug.inventory.movement"
                    ) or "New"
                )
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("sedar_movement_internal"):
            return super().write(vals)
        self._check_authority()
        if self.filtered(lambda record: record.state != "draft"):
            raise AccessError(_("Completed Tug Inventory Movements are immutable."))
        if {"state", "stock_move_id", "completed_by_id", "completed_at",
            "reason_label", "reversal_of_id", "reversal_id"}.intersection(vals):
            raise AccessError(_("Use the controlled movement actions."))
        return super().write(vals)

    def unlink(self):
        self._check_authority()
        if self.filtered(lambda record: record.state != "draft"):
            raise AccessError(_("Completed Tug Inventory Movements cannot be deleted."))
        return super().unlink()

    @api.model
    def _check_authority(self):
        groups = (
            "sedar_marine_operations.group_tug_master",
            "sedar_marine_operations.group_operations_manager",
            "sedar_marine_maintenance.group_marine_maintenance_user",
            "sedar_marine_inventory.group_marine_inventory_manager",
        )
        if not self.env.su and not any(self.env.user.has_group(group) for group in groups):
            raise AccessError(_("Your role cannot record Tug Inventory Movements."))

    @api.constrains("reason_code", "note")
    def _check_other_reason(self):
        for movement in self:
            if movement.reason_code == "other" and not (movement.note or "").strip():
                raise ValidationError(_("Other requires an explanatory note."))

    @api.constrains(
        "company_id", "product_id", "lot_id", "source_location_id",
        "destination_location_id",
    )
    def _check_company_contract(self):
        for movement in self:
            if movement.source_location_id == movement.destination_location_id:
                raise ValidationError(_("Source and destination must be different."))
            for record in (
                movement.product_id, movement.lot_id, movement.source_location_id,
                movement.destination_location_id,
            ):
                if record and record.company_id and record.company_id != movement.company_id:
                    raise ValidationError(_("Movement records must belong to one company."))

    def _validate_route(self):
        self.ensure_one()
        self.product_id._sedar_validate_inventory_action(self.action)
        self.product_id._sedar_validate_inventory_quantity(self.quantity)
        if self.product_id.sedar_item_type == "replacement_equipment" and not self.lot_id:
            raise UserError(_("Replacement Equipment requires its serial number."))
        destination_tug = self.destination_tugboat_id
        if (
            destination_tug
            and self.product_id.sedar_compatibility_scope == "restricted"
            and destination_tug not in self.product_id.sedar_compatible_tugboat_ids
        ):
            raise UserError(_("The Item Type is not compatible with the destination tugboat."))
        if self.action == "correct" and float_compare(
            abs(self.counted_qty - self.count_before_qty),
            self.quantity,
            precision_rounding=self.product_uom_id.rounding,
        ):
            raise UserError(_("The correction quantity must equal the physical-count difference."))
        if self.action == "correct":
            increase = float_compare(
                self.counted_qty,
                self.count_before_qty,
                precision_rounding=self.product_uom_id.rounding,
            ) > 0
            if increase != (
                self.source_location_id.sedar_location_role == "adjustment"
            ):
                raise UserError(_("The correction route does not match the count direction."))
        source_condition = self._condition(self.source_location_id)
        destination_condition = self._condition(self.destination_location_id)
        if self.reversal_of_id:
            valid = True
        elif self.action == "mark_defective":
            valid = (
                source_condition == "serviceable"
                and destination_condition == "defective"
                and self.source_tugboat_id == self.destination_tugboat_id
            )
        elif self.action == "return_service":
            valid = (
                source_condition == "defective"
                and destination_condition == "serviceable"
                and self.source_tugboat_id == self.destination_tugboat_id
            )
        elif self.action == "correct":
            valid = (
                self.source_location_id.sedar_location_role == "adjustment"
                and bool(destination_condition)
            ) or (
                self.destination_location_id.sedar_location_role == "adjustment"
                and bool(source_condition)
            )
        elif source_condition and destination_condition:
            valid = source_condition == destination_condition
        else:
            valid = self.action in {"consume", "dispose", "install", "remove"}
        if not valid:
            raise UserError(_("The selected route would change condition implicitly."))

    def _validate_availability(self):
        self.ensure_one()
        if self.source_location_id.usage != "internal":
            return
        available = self.env["stock.quant"]._get_available_quantity(
            self.product_id, self.source_location_id,
            lot_id=self.lot_id, strict=True,
        )
        if float_compare(
            self.quantity, available,
            precision_rounding=self.product_uom_id.rounding,
        ) > 0:
            raise UserError(_("The source has insufficient unreserved stock."))

    def action_complete(self):
        self.ensure_one()
        self._check_authority()
        self.env.cr.execute(
            "SELECT id FROM sedar_tug_inventory_movement WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()
        if self.state != "draft":
            raise UserError(_("Only a draft movement can be completed."))
        self._validate_route()
        self._validate_availability()
        if (
            self.source_will_be_blocked
            and not self.source_shortage_acknowledged
        ):
            raise UserError(_(
                "Acknowledge that this movement leaves the source tug below its baseline."
            ))
        move = self.env["sedar.inventory.lifecycle"]._create_done_stock_move(
            self.product_id,
            self.quantity,
            self.source_location_id,
            self.destination_location_id,
            self.name,
            self.company_id,
            self.lot_id,
        )
        reason_label = dict(MOVEMENT_REASONS)[self.reason_code]
        self.with_context(sedar_movement_internal=True).write({
            "state": "done",
            "reason_label": reason_label,
            "stock_move_id": move.id,
            "completed_by_id": self.env.user.id,
            "completed_at": fields.Datetime.now(),
        })
        self._create_history()
        self.env["sedar.replenishment.demand"]._sync_inventory_shortages()
        return True

    def action_reverse(self):
        self.ensure_one()
        self._check_authority()
        if self.state != "done" or self.reversal_id:
            raise UserError(_("Only an unreversed completed movement can be reversed."))
        reversal = self.create({
            "company_id": self.company_id.id,
            "action": "transfer",
            "product_id": self.product_id.id,
            "quantity": self.quantity,
            "lot_id": self.lot_id.id,
            "source_location_id": self.destination_location_id.id,
            "destination_location_id": self.source_location_id.id,
            "reason_code": "inventory_correction",
            "note": _("Reversal of %s") % self.name,
            "reversal_of_id": self.id,
            "source_shortage_acknowledged": True,
        })
        reversal.action_complete()
        self.with_context(sedar_movement_internal=True).write({
            "state": "reversed",
            "reversal_id": reversal.id,
        })
        return reversal

    def _create_history(self):
        self.ensure_one()
        History = self.env["sedar.tug.inventory.history"].sudo().with_context(
            sedar_history_create=True
        )
        if self.action == "correct":
            tugboat = self.source_tugboat_id or self.destination_tugboat_id
            if tugboat:
                History.create(self._history_values(tugboat, "correction"))
            return
        if self.source_tugboat_id:
            History.create(self._history_values(self.source_tugboat_id, "outgoing"))
        if self.destination_tugboat_id:
            perspective = (
                "condition"
                if self.destination_tugboat_id == self.source_tugboat_id
                else "incoming"
            )
            if perspective != "condition" or not self.source_tugboat_id:
                History.create(self._history_values(self.destination_tugboat_id, perspective))
            elif self.source_tugboat_id:
                self.history_ids.filtered(
                    lambda row: row.tugboat_id == self.source_tugboat_id
                ).with_context(sedar_history_internal=True).write({
                    "perspective": "condition",
                    "event_text": self._event_text("condition"),
                })

    def _history_values(self, tugboat, perspective):
        return {
            "movement_id": self.id,
            "company_id": self.company_id.id,
            "tugboat_id": tugboat.id,
            "perspective": perspective,
            "event_text": self._event_text(perspective),
        }

    def _event_text(self, perspective):
        quantity = "%g %s" % (self.quantity, self.product_uom_id.display_name)
        if perspective == "correction":
            return _(
                "Physical count changed %(product)s from %(before)g to %(counted)g %(unit)s (%(delta)s%(quantity)s).",
                product=self.product_id.display_name,
                before=self.count_before_qty,
                counted=self.counted_qty,
                unit=self.product_uom_id.display_name,
                delta="+" if self.counted_qty > self.count_before_qty else "-",
                quantity="%g" % self.quantity,
            )
        if perspective == "incoming":
            return _("%(quantity)s %(product)s received from %(source)s.",
                quantity=quantity, product=self.product_id.display_name,
                source=self.source_location_id.display_name)
        if perspective == "condition":
            return _("%(quantity)s %(product)s changed from %(source)s to %(destination)s.",
                quantity=quantity, product=self.product_id.display_name,
                source=self.source_condition, destination=self.destination_condition)
        return _("%(quantity)s %(product)s moved to %(destination)s.",
            quantity=quantity, product=self.product_id.display_name,
            destination=self.destination_location_id.display_name)

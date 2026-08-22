from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


CLOSING_EVENT_TYPES = {"return", "consume", "dispose"}


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    sedar_inventory_product_id = fields.Many2one(
        "product.product",
        string="Originating Item Type",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )
    sedar_inventory_lot_id = fields.Many2one(
        "stock.lot",
        string="Originating Serial Number",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )
    sedar_inventory_current_lifecycle_id = fields.Many2one(
        "sedar.inventory.lifecycle",
        string="Current Inventory Lifecycle",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )

    _sedar_inventory_identity_unique = models.Constraint(
        "UNIQUE(sedar_inventory_product_id, sedar_inventory_lot_id)",
        "A product and serial number may identify only one Equipment record.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        protected = {
            "sedar_inventory_product_id",
            "sedar_inventory_lot_id",
            "sedar_inventory_current_lifecycle_id",
        }
        if (
            any(protected.intersection(vals) for vals in vals_list)
            and not self.env.context.get("sedar_inventory_equipment_write")
        ):
            raise AccessError(
                _("Equipment inventory provenance is created only by controlled installation.")
            )
        return super().create(vals_list)

    def write(self, vals):
        provenance = {"sedar_inventory_product_id", "sedar_inventory_lot_id"}
        if provenance.intersection(vals) and not self.env.context.get(
            "sedar_inventory_equipment_write"
        ):
            for equipment in self:
                if any(equipment[field_name] for field_name in provenance):
                    raise AccessError(_("Equipment inventory provenance is immutable."))
        if (
            "sedar_inventory_current_lifecycle_id" in vals
            and not self.env.context.get("sedar_inventory_equipment_write")
        ):
            raise AccessError(_("Equipment installation provenance is controlled by Inventory."))
        return super().write(vals)


class SedarInventoryLifecycle(models.Model):
    _name = "sedar.inventory.lifecycle"
    _description = "SEDAR Tugboat Inventory Lifecycle"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issued_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(related="issue_id.name", store=True, readonly=True)
    issue_id = fields.Many2one(
        "sedar.inventory.issue", required=True, readonly=True, copy=False, ondelete="restrict"
    )
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, index=True, copy=False
    )
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    product_uom_id = fields.Many2one("uom.uom", required=True, readonly=True, ondelete="restrict")
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, readonly=True, index=True,
        ondelete="restrict", check_company=True,
    )
    source_location_id = fields.Many2one(
        "stock.location", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    tug_location_id = fields.Many2one(
        "stock.location", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    issue_move_id = fields.Many2one(
        "stock.move", required=True, readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    initial_qty = fields.Float(required=True, readonly=True)
    open_qty = fields.Float(compute="_compute_quantity_status", store=True, readonly=True)
    state = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        compute="_compute_quantity_status",
        store=True,
        readonly=True,
    )
    usage_state = fields.Selection(
        [
            ("onboard", "Onboard"),
            ("assigned", "Assigned"),
            ("installed", "Installed"),
            ("removed", "Removed"),
            ("closed", "Closed"),
        ],
        required=True,
        default="onboard",
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot", string="Serial / Lot", readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment", readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    issued_by_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    issued_at = fields.Datetime(required=True, readonly=True)
    installed_at = fields.Datetime(compute="_compute_technical_dates", store=True, readonly=True)
    removed_at = fields.Datetime(compute="_compute_technical_dates", store=True, readonly=True)
    reconciliation_state = fields.Selection(
        [("reconciled", "Reconciled"), ("warning", "Needs Review")],
        compute="_compute_quantity_status",
        store=True,
        readonly=True,
    )
    event_ids = fields.One2many(
        "sedar.inventory.lifecycle.event", "lifecycle_id", readonly=True, copy=False
    )
    disposition_activity_id = fields.Many2one(
        "mail.activity", readonly=True, copy=False, ondelete="set null"
    )
    serial_open_key = fields.Char(
        compute="_compute_serial_open_key", store=True, readonly=True, copy=False
    )

    _issue_unique = models.Constraint(
        "UNIQUE(issue_id)", "An Inventory Issue may have only one lifecycle."
    )
    _open_replacement_serial_unique = models.Constraint(
        "UNIQUE(serial_open_key)",
        "A serialized Item Type may have only one open inventory lifecycle.",
    )

    @api.depends("product_id", "lot_id", "state")
    def _compute_serial_open_key(self):
        for lifecycle in self:
            lifecycle.serial_open_key = (
                "%s:%s" % (lifecycle.product_id.id, lifecycle.lot_id.id)
                if (
                    lifecycle.product_id.sedar_item_type == "replacement_equipment"
                    and lifecycle.lot_id
                    and lifecycle.state == "open"
                )
                else False
            )

    @api.depends("initial_qty", "product_uom_id.rounding", "event_ids.event_type", "event_ids.quantity", "event_ids.stock_move_id.state")
    def _compute_quantity_status(self):
        for lifecycle in self:
            closed_qty = sum(
                event.quantity
                for event in lifecycle.event_ids
                if event.event_type in CLOSING_EVENT_TYPES and event.stock_move_id.state == "done"
            )
            lifecycle.open_qty = max(lifecycle.initial_qty - closed_qty, 0.0)
            lifecycle.state = (
                "closed"
                if float_is_zero(lifecycle.open_qty, precision_rounding=lifecycle.product_uom_id.rounding)
                else "open"
            )
            moves = lifecycle.issue_move_id | lifecycle.event_ids.mapped("stock_move_id")
            lifecycle.reconciliation_state = (
                "reconciled" if moves and all(move.state == "done" for move in moves) else "warning"
            )

    @api.depends("event_ids.event_type", "event_ids.event_at")
    def _compute_technical_dates(self):
        for lifecycle in self:
            installs = lifecycle.event_ids.filtered(lambda event: event.event_type == "install")
            removals = lifecycle.event_ids.filtered(lambda event: event.event_type == "remove")
            lifecycle.installed_at = max(installs.mapped("event_at"), default=False)
            lifecycle.removed_at = max(removals.mapped("event_at"), default=False)

    @api.constrains(
        "company_id", "product_id", "product_uom_id", "tugboat_id", "source_location_id",
        "tug_location_id", "issue_move_id", "initial_qty", "lot_id",
    )
    def _check_lifecycle_contract(self):
        for lifecycle in self:
            lifecycle._validate_company_locations()
            if lifecycle.initial_qty <= 0:
                raise ValidationError(_("The issued quantity must be greater than zero."))
            if not lifecycle.product_uom_id._has_common_reference(
                lifecycle.product_id.uom_id
            ):
                raise ValidationError(_("The lifecycle unit must be compatible with the Item Type unit."))
            if lifecycle.issue_move_id.state != "done":
                raise ValidationError(_("A lifecycle requires a completed issue stock movement."))
            lifecycle._validate_issue_move()
            lifecycle._validate_replacement_equipment()

    def _validate_issue_move(self):
        self.ensure_one()
        move = self.issue_move_id
        rounding = self.product_uom_id.rounding
        if (
            move.company_id != self.company_id
            or move.product_id != self.product_id
            or move.location_id != self.source_location_id
            or move.location_dest_id != self.tug_location_id
            or float_compare(
                move.quantity, self.initial_qty, precision_rounding=rounding
            )
            != 0
        ):
            raise ValidationError(
                _("The completed issue move must exactly match the lifecycle facts.")
            )
        move_lots = move.move_line_ids.mapped("lot_id")
        if self.lot_id and move_lots != self.lot_id:
            raise ValidationError(
                _("The completed issue move must use the lifecycle serial or lot.")
            )

    def _validate_company_locations(self):
        self.ensure_one()
        product_company = self.product_id.company_id
        tug_company = getattr(self.tugboat_id, "company_id", False)
        if product_company and product_company != self.company_id:
            raise ValidationError(_("The Item Type must be shared or belong to the lifecycle company."))
        if tug_company and tug_company != self.company_id:
            raise ValidationError(_("The tugboat must belong to the lifecycle company."))
        if self.source_location_id.company_id != self.company_id:
            raise ValidationError(_("The Storage location must belong to the lifecycle company."))
        if self.source_location_id.sedar_location_role != "storage":
            raise ValidationError(_("Inventory may be issued only from a tagged Storage location."))
        if (
            self.tug_location_id.company_id != self.company_id
            or self.tug_location_id.sedar_location_role != "tug"
            or self.tug_location_id.sedar_tugboat_id != self.tugboat_id
        ):
            raise ValidationError(_("The destination must be this tugboat's tagged stock location."))

    def _validate_replacement_equipment(self):
        self.ensure_one()
        if self.product_id.sedar_item_type != "replacement_equipment":
            return
        if self.product_id.tracking != "serial" or not self.lot_id:
            raise ValidationError(_("Replacement Equipment requires a tracked serial number."))
        if float_compare(
            self.initial_qty, 1.0, precision_rounding=self.product_uom_id.rounding
        ) != 0:
            raise ValidationError(_("Replacement Equipment must be issued one serialized unit at a time."))
        if self.lot_id.product_id != self.product_id:
            raise ValidationError(_("The selected serial number belongs to another Item Type."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sedar_inventory_lifecycle_create"):
            raise AccessError(_("Inventory lifecycles are created only by the controlled issue action."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("sedar_inventory_lifecycle_write"):
            raise AccessError(_("Inventory lifecycle facts cannot be edited directly."))
        allowed = {
            "usage_state",
            "equipment_id",
            "disposition_activity_id",
            "serial_open_key",
        }
        if set(vals) - allowed:
            raise AccessError(_("Immutable inventory lifecycle facts cannot be changed."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Inventory lifecycles cannot be deleted."))

    def _lock_and_reload(self):
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM sedar_inventory_lifecycle WHERE id IN %s FOR UPDATE",
            [tuple(self.ids)],
        )
        self.invalidate_recordset(["open_qty", "state", "usage_state", "event_ids"])

    def _check_exact_officer(self):
        self.ensure_one()
        officer = self.company_id.sedar_procurement_inventory_officer_id
        if not officer or self.env.user != officer:
            raise AccessError(_(
                "Only this company's configured Procurement and Inventory Officer may perform this inventory action."
            ))

    def _check_maintenance_manager(self):
        if not self.env.user.has_group("sedar_marine_maintenance.group_marine_maintenance_manager"):
            raise AccessError(_("Only a Marine Maintenance Manager may perform this technical action."))

    def _create_event(self, event_type, quantity=0.0, reason=None, stock_move=None):
        self.ensure_one()
        actor_id = self.env.user.id
        return self.env["sedar.inventory.lifecycle.event"].sudo().with_context(
            sedar_inventory_event_create=True
        ).create({
            "lifecycle_id": self.id,
            "event_type": event_type,
            "quantity": quantity,
            "reason": reason,
            "stock_move_id": stock_move.id if stock_move else False,
            "actor_id": actor_id,
            "event_at": fields.Datetime.now(),
        })

    def action_assign(self, equipment=None):
        for lifecycle in self:
            lifecycle._check_maintenance_manager()
            lifecycle._lock_and_reload()
            if lifecycle.state != "open" or lifecycle.usage_state not in {"onboard", "removed"}:
                raise UserError(_("Only open onboard or removed inventory can be assigned."))
            lifecycle._validate_assignment_equipment(equipment)
            lifecycle._create_event("assign")
            lifecycle.with_context(sedar_inventory_lifecycle_write=True).write({
                "usage_state": "assigned",
                "equipment_id": equipment.id if equipment else False,
            })
        return True

    def _validate_assignment_equipment(self, equipment):
        self.ensure_one()
        if not equipment:
            return
        if len(equipment) != 1:
            raise UserError(_("Select one Equipment record for this assignment."))
        if self.product_id.sedar_item_type == "replacement_equipment":
            raise UserError(
                _("Replacement Equipment receives its Equipment identity during installation.")
            )
        if equipment.company_id != self.company_id:
            raise UserError(_("The selected Equipment belongs to another company."))
        if equipment.sedar_tugboat_id != self.tugboat_id:
            raise UserError(_("The selected Equipment must be installed on this tugboat."))

    def action_install(self):
        for lifecycle in self:
            lifecycle._check_maintenance_manager()
            lifecycle._lock_and_reload()
            lifecycle._validate_install_state()
            equipment = lifecycle._find_or_create_equipment()
            lifecycle._create_event("install")
            lifecycle.with_context(sedar_inventory_lifecycle_write=True).write({
                "usage_state": "installed",
                "equipment_id": equipment.id,
            })
        return True

    def _validate_install_state(self):
        self.ensure_one()
        if self.product_id.sedar_item_type != "replacement_equipment":
            raise UserError(_("Only Replacement Equipment becomes tracked Equipment on installation."))
        if self.state != "open" or self.usage_state not in {"onboard", "assigned", "removed"}:
            raise UserError(_("This serialized unit is not available for installation."))
        self._validate_replacement_equipment()

    def _find_or_create_equipment(self):
        self.ensure_one()
        equipment = self.equipment_id or self.env["maintenance.equipment"].search([
            ("sedar_inventory_product_id", "=", self.product_id.id),
            ("sedar_inventory_lot_id", "=", self.lot_id.id),
        ], limit=1)
        values = {
            "sedar_tugboat_id": self.tugboat_id.id,
            "sedar_inventory_current_lifecycle_id": self.id,
        }
        if equipment:
            equipment.with_context(sedar_inventory_equipment_write=True).write(values)
            return equipment
        values.update({
            "name": "%s / %s" % (self.product_id.display_name, self.lot_id.name),
            "company_id": self.company_id.id,
            "sedar_installation_date": fields.Date.context_today(self),
            "sedar_inventory_product_id": self.product_id.id,
            "sedar_inventory_lot_id": self.lot_id.id,
        })
        return self.env["maintenance.equipment"].with_context(
            sedar_inventory_equipment_write=True
        ).create(values)

    def action_remove(self):
        for lifecycle in self:
            lifecycle._check_maintenance_manager()
            lifecycle._lock_and_reload()
            if lifecycle.state != "open" or lifecycle.usage_state != "installed":
                raise UserError(_("Only installed open inventory can be technically removed."))
            lifecycle._create_event("remove")
            lifecycle.with_context(sedar_inventory_lifecycle_write=True).write({"usage_state": "removed"})
            lifecycle.equipment_id.with_context(
                sedar_inventory_equipment_write=True
            ).write({
                "sedar_tugboat_id": False,
                "sedar_inventory_current_lifecycle_id": False,
            })
            lifecycle._schedule_disposition_activity()
        return True

    def _schedule_disposition_activity(self):
        self.ensure_one()
        officer = self.company_id.sedar_procurement_inventory_officer_id
        if not officer or self.disposition_activity_id:
            return
        activity = self.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=officer.id,
            summary=_("Decide disposition for removed inventory"),
            note=_(
                "%(item)s was removed from %(tug)s and remains onboard pending return, consumption, or disposal.",
                item=self.product_id.display_name,
                tug=self.tugboat_id.display_name,
            ),
        )
        self.with_context(sedar_inventory_lifecycle_write=True).write({
            "disposition_activity_id": activity.id
        })

    def action_return(self, quantity, reason):
        return self._action_close("return", quantity, reason)

    def action_consume(self, quantity, reason):
        return self._action_close("consume", quantity, reason)

    def action_dispose(self, quantity, reason):
        return self._action_close("dispose", quantity, reason)

    def _action_close(self, event_type, quantity, reason):
        for lifecycle in self:
            lifecycle._check_exact_officer()
            lifecycle._lock_and_reload()
            lifecycle._validate_close_request(quantity, reason)
            destination = lifecycle._closing_destination(event_type)
            move = lifecycle._create_done_stock_move(
                lifecycle.product_id,
                quantity,
                lifecycle.tug_location_id,
                destination,
                "%s - %s" % (lifecycle.name, event_type.title()),
                lifecycle.company_id,
                lifecycle.lot_id,
            )
            lifecycle._create_event(event_type, quantity, reason.strip(), move)
            lifecycle.invalidate_recordset(["open_qty", "state", "reconciliation_state"])
            if lifecycle.state == "closed":
                lifecycle.with_context(sedar_inventory_lifecycle_write=True).write({"usage_state": "closed"})
                lifecycle.with_context(
                    sedar_inventory_lifecycle_write=True
                )._compute_serial_open_key()
                lifecycle.flush_recordset(["state", "serial_open_key"])
                lifecycle._close_disposition_activity()
        return True

    def _close_disposition_activity(self):
        self.ensure_one()
        activity = self.disposition_activity_id.exists()
        if activity:
            activity.action_done()
        self.with_context(sedar_inventory_lifecycle_write=True).write({
            "disposition_activity_id": False
        })

    def _validate_close_request(self, quantity, reason):
        self.ensure_one()
        rounding = self.product_uom_id.rounding
        if float_compare(quantity, 0.0, precision_rounding=rounding) <= 0:
            raise UserError(_("The disposition quantity must be greater than zero."))
        if float_compare(quantity, self.open_qty, precision_rounding=rounding) > 0:
            raise UserError(_("The disposition quantity cannot exceed the open quantity."))
        if not reason or not reason.strip():
            raise UserError(_("A disposition reason is required."))
        if self.usage_state == "installed":
            raise UserError(_("Installed Equipment must be technically removed before disposition."))
        if self.product_id.sedar_item_type == "replacement_equipment" and float_compare(
            quantity, self.open_qty, precision_rounding=rounding
        ) != 0:
            raise UserError(_("Serialized Replacement Equipment cannot be partially closed."))
        physical = self._available_quantity(
            self.product_id, self.tug_location_id, self.lot_id
        )
        if float_compare(quantity, physical, precision_rounding=rounding) > 0:
            raise UserError(_("The tugboat location does not have enough unreserved physical stock."))

    def _closing_destination(self, event_type):
        self.ensure_one()
        destination = {
            "return": self.company_id.sedar_default_storage_location_id,
            "consume": self.company_id.sedar_consumption_location_id,
            "dispose": self.company_id.sedar_disposal_location_id,
        }[event_type]
        expected_role = {"return": "storage", "consume": "consumption", "dispose": "disposal"}[event_type]
        if not destination or destination.sedar_location_role != expected_role:
            raise UserError(_("Configure the company's matching SEDAR destination location first."))
        if destination.company_id != self.company_id:
            raise UserError(_("The destination location belongs to another company."))
        return destination

    @api.model
    def _available_quantity(self, product, location, lot=None):
        return self.env["stock.quant"]._get_available_quantity(
            product, location, lot_id=lot, strict=True
        )

    @api.model
    def _create_done_stock_move(
        self, product, quantity, source, destination, origin, company, lot=None
    ):
        move = self.env["stock.move"].with_company(company).create({
            "origin": origin,
            "company_id": company.id,
            "product_id": product.id,
            "product_uom_qty": quantity,
            "product_uom": product.uom_id.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
        })
        move._action_confirm()
        if lot:
            reserved = move._update_reserved_quantity(
                quantity, source, lot_id=lot, strict=True
            )
            if float_compare(
                reserved, quantity, precision_rounding=product.uom_id.rounding
            ) != 0:
                raise UserError(_("Odoo could not reserve the selected serial or lot."))
        move._action_assign()
        lines = move.move_line_ids.filtered(lambda line: not lot or line.lot_id == lot)
        if (
            not lines
            or float_compare(
                move.quantity, quantity, precision_rounding=product.uom_id.rounding
            ) != 0
        ):
            raise UserError(_("Odoo could not reserve the requested physical stock."))
        if lot and (
            len(lines) != 1
            or lines.lot_id != lot
            or len(move.move_line_ids) != len(lines)
        ):
            raise UserError(_("Odoo could not reserve the selected serial number."))
        move.picked = True
        move._action_done()
        move.invalidate_recordset(["state"])
        if move.state != "done":
            raise UserError(_("The inventory movement could not be completed."))
        return move


class SedarInventoryLifecycleEvent(models.Model):
    _name = "sedar.inventory.lifecycle.event"
    _description = "SEDAR Inventory Lifecycle Event"
    _order = "event_at, id"
    _check_company_auto = True

    lifecycle_id = fields.Many2one(
        "sedar.inventory.lifecycle", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    company_id = fields.Many2one(
        related="lifecycle_id.company_id", store=True, readonly=True, index=True
    )
    event_type = fields.Selection(
        [
            ("assign", "Assigned"),
            ("install", "Installed"),
            ("remove", "Technically Removed"),
            ("return", "Returned to Storage"),
            ("consume", "Consumed"),
            ("dispose", "Disposed"),
        ],
        required=True,
        readonly=True,
    )
    quantity = fields.Float(required=True, readonly=True, default=0.0)
    product_uom_id = fields.Many2one(
        related="lifecycle_id.product_uom_id", store=True, readonly=True
    )
    stock_move_id = fields.Many2one(
        "stock.move", readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    actor_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    event_at = fields.Datetime(required=True, readonly=True)
    reason = fields.Text(readonly=True)

    @api.constrains("event_type", "quantity", "stock_move_id", "reason")
    def _check_event_contract(self):
        for event in self:
            closing = event.event_type in CLOSING_EVENT_TYPES
            if closing and (
                event.quantity <= 0
                or not event.stock_move_id
                or event.stock_move_id.state != "done"
                or not event.reason
            ):
                raise ValidationError(_(
                    "A closing lifecycle event requires a positive quantity, reason, and completed stock move."
                ))
            if not closing and (event.quantity or event.stock_move_id):
                raise ValidationError(_("Technical lifecycle events cannot change stock quantity."))
            if closing:
                event._validate_closing_move()

    def _validate_closing_move(self):
        self.ensure_one()
        lifecycle = self.lifecycle_id
        move = self.stock_move_id
        expected_destination = {
            "return": lifecycle.company_id.sedar_default_storage_location_id,
            "consume": lifecycle.company_id.sedar_consumption_location_id,
            "dispose": lifecycle.company_id.sedar_disposal_location_id,
        }[self.event_type]
        if (
            move.company_id != lifecycle.company_id
            or move.product_id != lifecycle.product_id
            or move.location_id != lifecycle.tug_location_id
            or move.location_dest_id != expected_destination
            or float_compare(
                move.quantity,
                self.quantity,
                precision_rounding=lifecycle.product_uom_id.rounding,
            )
            != 0
        ):
            raise ValidationError(
                _("The completed stock move must exactly match the closing event.")
            )
        move_lots = move.move_line_ids.mapped("lot_id")
        if lifecycle.lot_id and move_lots != lifecycle.lot_id:
            raise ValidationError(
                _("The closing stock move must use the lifecycle serial or lot.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sedar_inventory_event_create"):
            raise AccessError(_("Lifecycle events are created only by controlled inventory actions."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Inventory lifecycle events are immutable."))

    def unlink(self):
        raise AccessError(_("Inventory lifecycle events cannot be deleted."))

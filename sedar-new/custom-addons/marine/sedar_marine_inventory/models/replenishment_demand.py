from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SedarReplenishmentDemand(models.Model):
    _name = "sedar.replenishment.demand"
    _description = "Inventory Replenishment Demand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "state, required_date, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False)
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, index=True,
    )
    scope = fields.Selection(
        [("baseline", "Baseline"), ("operation", "Operation")],
        required=True, readonly=True, index=True,
    )
    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, readonly=True, check_company=True,
        ondelete="restrict", index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True, check_company=True,
        ondelete="restrict", index=True,
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    stock_requirement_id = fields.Many2one(
        "sedar.tug.stock.requirement", readonly=True, check_company=True,
        ondelete="restrict",
    )
    inventory_requirement_id = fields.Many2one(
        "sedar.inventory.requirement", readonly=True, check_company=True,
        ondelete="restrict",
    )
    tug_assignment_id = fields.Many2one(
        "sedar.tug.assignment", readonly=True, check_company=True,
        ondelete="restrict",
    )
    order_id = fields.Many2one(
        "sedar.marine.service.order", readonly=True, check_company=True,
        ondelete="restrict",
    )
    required_qty = fields.Float(readonly=True)
    serviceable_qty = fields.Float(readonly=True)
    original_shortage_qty = fields.Float(readonly=True)
    fulfilled_qty = fields.Float(readonly=True)
    remaining_qty = fields.Float(readonly=True)
    required_date = fields.Date(readonly=True, index=True)
    state = fields.Selection(
        [("open", "Open"), ("fulfilled", "Fulfilled"),
         ("no_longer_required", "No Longer Required")],
        required=True, default="open", readonly=True, index=True,
    )
    opened_at = fields.Datetime(required=True, readonly=True)
    closed_at = fields.Datetime(readonly=True)
    closure_reason = fields.Char(readonly=True)
    movement_ids = fields.One2many(
        "sedar.tug.inventory.movement", "demand_id", readonly=True,
    )
    active_key = fields.Char(readonly=True, copy=False, index=True)

    _active_key_unique = models.Constraint(
        "UNIQUE(active_key)",
        "Only one open Replenishment Demand may exist for a requirement.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get("sedar_demand_sync")):
            raise AccessError(_("Replenishment Demands are created from shortages."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("sedar_demand_sync"):
            return super().write(vals)
        raise AccessError(_("Replenishment Demands are maintained from shortages."))

    def unlink(self):
        raise AccessError(_("Replenishment Demand history cannot be deleted."))

    @api.model
    def _sync_inventory_shortages(self):
        active_keys = set()
        Tugboat = self.env["sedar.tugboat"].with_context(active_test=False)
        for tugboat in Tugboat.search([("stock_location_id", "!=", False)]):
            for requirement in self.env["sedar.tug.stock.requirement"]._effective_for_tug(
                tugboat
            ):
                key = ("baseline", tugboat.id, requirement.product_id.id,
                       requirement.id)
                active_keys.add(key)
                available = self.env["stock.quant"]._get_available_quantity(
                    requirement.product_id, tugboat.stock_location_id, strict=True
                )
                self._sync_one(
                    "baseline", tugboat, requirement.product_id,
                    requirement.required_qty, available,
                    stock_requirement=requirement,
                    required_date=fields.Date.context_today(self),
                )
        operation_lines = self.env["sedar.inventory.requirement"].search([
            ("tugboat_id", "!=", False),
            ("product_id.sedar_readiness_critical", "=", True),
            ("tug_assignment_id.state", "!=", "cancelled"),
            ("order_id.state", "!=", "cancelled"),
        ])
        for line in operation_lines:
            key = ("operation", line.tugboat_id.id, line.product_id.id, line.id)
            active_keys.add(key)
            planned = line.tug_assignment_id.planned_start
            required_date = fields.Date.to_date(planned) if planned else fields.Date.context_today(self)
            self._sync_one(
                "operation", line.tugboat_id, line.product_id,
                line.required_qty, line.available_qty,
                inventory_requirement=line,
                required_date=required_date,
            )
        for demand in self.search([("state", "=", "open")]):
            source_id = (
                demand.stock_requirement_id.id
                if demand.scope == "baseline"
                else demand.inventory_requirement_id.id
            )
            key = (demand.scope, demand.tugboat_id.id, demand.product_id.id, source_id)
            if key not in active_keys:
                demand._close("no_longer_required", "The originating requirement no longer applies.")
        return True

    @api.model
    def _sync_one(self, scope, tugboat, product, required, available,
                  stock_requirement=None, inventory_requirement=None,
                  required_date=None):
        shortage = max(required - available, 0.0)
        domain = [
            ("state", "=", "open"), ("scope", "=", scope),
            ("tugboat_id", "=", tugboat.id), ("product_id", "=", product.id),
        ]
        if stock_requirement:
            domain.append(("stock_requirement_id", "=", stock_requirement.id))
        if inventory_requirement:
            domain.append(("inventory_requirement_id", "=", inventory_requirement.id))
        demand = self.search(domain, limit=1)
        if not shortage:
            if demand:
                demand._close("fulfilled", "Serviceable onboard stock satisfies the requirement.")
            return demand
        values = {
            "required_qty": required,
            "serviceable_qty": available,
            "remaining_qty": shortage,
            "original_shortage_qty": max(
                demand.original_shortage_qty if demand else shortage, shortage
            ),
            "required_date": required_date,
        }
        values["fulfilled_qty"] = max(
            values["original_shortage_qty"] - shortage, 0.0
        )
        source_id = stock_requirement.id if stock_requirement else inventory_requirement.id
        values["active_key"] = "%s:%s:%s:%s" % (
            scope, tugboat.id, product.id, source_id
        )
        Demand = self.sudo().with_context(sedar_demand_sync=True)
        if demand:
            demand.sudo().with_context(sedar_demand_sync=True).write(values)
        else:
            values.update({
                "name": "%s / %s / %s" % (
                    "Baseline" if scope == "baseline" else "Operation",
                    tugboat.display_name, product.display_name,
                ),
                "company_id": tugboat.company_id.id,
                "scope": scope,
                "tugboat_id": tugboat.id,
                "product_id": product.id,
                "stock_requirement_id": stock_requirement.id if stock_requirement else False,
                "inventory_requirement_id": inventory_requirement.id if inventory_requirement else False,
                "tug_assignment_id": inventory_requirement.tug_assignment_id.id if inventory_requirement else False,
                "order_id": inventory_requirement.order_id.id if inventory_requirement else False,
                "original_shortage_qty": shortage,
                "opened_at": fields.Datetime.now(),
            })
            demand = Demand.create(values)
        demand.sudo()._sync_activity()
        return demand

    def _sync_activity(self):
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for demand in self:
            officer = demand.company_id.sedar_procurement_inventory_officer_id
            if not officer:
                continue
            activity = demand.activity_ids.filtered(
                lambda row: row.activity_type_id == activity_type
                and row.user_id == officer
            )[:1]
            values = {
                "summary": "Resolve inventory shortage",
                "date_deadline": demand.required_date,
            }
            if activity:
                activity.write(values)
            else:
                demand.activity_schedule("mail.mail_activity_data_todo", user_id=officer.id, **values)

    def _close(self, state, reason):
        demands = self.sudo()
        demands.with_context(sedar_demand_sync=True).write({
            "state": state,
            "remaining_qty": 0.0 if state == "fulfilled" else self.remaining_qty,
            "closed_at": fields.Datetime.now(),
            "closure_reason": reason,
            "active_key": False,
        })
        demands.activity_ids.action_done()

    def action_resolve_shortage(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Resolve Shortage",
            "res_model": "sedar.inventory.shortage.resolve.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_demand_id": self.id},
        }

    def action_create_purchase_request(self):
        raise UserError(_("Install the SEDAR Purchase Request addon for procurement."))

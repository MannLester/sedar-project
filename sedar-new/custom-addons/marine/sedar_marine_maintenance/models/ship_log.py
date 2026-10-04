from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SedarShipLogEntry(models.Model):
    """One entry the offline ship log has already delivered, so a retried upload is never applied twice.

    The offline pages keep no business rules: they download a snapshot and upload entries, and this model
    applies them through the normal Daily Engine Report and Planned Maintenance completion rules.
    """

    _name = "sedar.ship.log.entry"
    _description = "Ship Log Entry"
    _order = "id desc"

    client_id = fields.Char(required=True, index=True, readonly=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    message = fields.Char(readonly=True)

    _one_entry_per_client_id = models.Constraint(
        "unique(client_id)", "This ship log entry was already received."
    )

    @api.model
    def _sedar_snapshot(self):
        """Everything the page needs to work without a connection."""
        tugs = []
        for tug in self.env["sedar.tugboat"].search([]):
            engines = self.env["maintenance.equipment"].search([
                ("sedar_tugboat_id", "=", tug.id),
                ("sedar_hours_from_id", "=", False),
                ("sedar_running_hour_reading_ids", "!=", False),
            ])
            tasks = self.env["sedar.pm.task"].search([("tugboat_id", "=", tug.id), ("state", "!=", "not_due")])
            tugs.append({
                "id": tug.id,
                "name": tug.name,
                "engines": [
                    {"id": engine.id, "name": engine.name, "hours": engine.sedar_current_running_hours}
                    for engine in engines
                ],
                "tasks": [
                    {
                        "id": task.id,
                        "name": task.name,
                        "equipment": task.equipment_id.name,
                        "state": task.state,
                        "next_checkpoint": task.next_checkpoint_hours,
                        "remaining": task.remaining_hours,
                    }
                    for task in tasks
                ],
            })
        return {
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "user": self.env.user.name,
            "tugs": tugs,
        }

    @api.model
    def _sedar_sync(self, items):
        """Apply each uploaded entry on its own; report per entry so one rejection never blocks the rest."""
        results = []
        for item in items:
            client_id = str(item.get("client_id") or "")
            try:
                with self.env.cr.savepoint():
                    existing = self.search([("client_id", "=", client_id)], limit=1)
                    message = existing.message if existing else self._sedar_apply(item)
                    if not existing:
                        self.create({"client_id": client_id, "message": message})
                results.append({"client_id": client_id, "ok": True, "message": message})
            except (UserError, ValidationError, AccessError) as error:
                results.append({"client_id": client_id, "ok": False, "message": str(error)})
            except (KeyError, TypeError, ValueError):
                results.append({"client_id": client_id, "ok": False, "message": _("The entry is incomplete.")})
        return results

    @api.model
    def _sedar_apply(self, item):
        kind = item["kind"]
        if kind == "report":
            report = self.env["sedar.daily.engine.report"]._sedar_save_log(item, submit=True)
            return _("Report %s submitted.", report.name)
        if kind == "completion":
            task = self.env["sedar.pm.task"].browse(item["task_id"]).exists()
            if not task:
                raise UserError(_("The task no longer exists."))
            self.env["sedar.pm.task.completion"].create({
                "task_id": task.id,
                "done_on": item["done_on"],
                "remarks": item.get("remarks"),
            })
            return _("%s recorded.", task.name)
        raise UserError(_("Unknown entry type."))

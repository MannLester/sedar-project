from odoo import fields, models
from odoo.exceptions import UserError


class SedarCrewShortageAction(models.Model):
    _inherit = "sedar.crew.shortage.action"

    action_type = fields.Selection(
        selection_add=[("temporary_reliever", "Temporary Reliever")],
        ondelete={"temporary_reliever": "cascade"},
    )
    relief_crew_profile_id = fields.Many2one("sedar.crew.profile", string="Relief Crew")
    relief_assignment_id = fields.Many2one("sedar.crew.assignment", readonly=True, copy=False)
    unavailability_id = fields.Many2one("sedar.crew.unavailability", readonly=True, copy=False)
    unavailability_start = fields.Datetime()
    unavailability_end = fields.Datetime()
    unavailability_reason = fields.Char()

    def action_complete(self):
        temporary = self.filtered(lambda action: action.action_type == "temporary_reliever")
        regular = self - temporary
        result = True
        if regular:
            result = super(SedarCrewShortageAction, regular).action_complete()
        for action in temporary:
            action._complete_temporary_reliever()
        return result

    def _complete_temporary_reliever(self):
        self.ensure_one()
        if not self.outcome:
            raise UserError("Enter the action outcome before completing it.")
        if not self.relief_crew_profile_id:
            raise UserError("Select a relief crew profile.")
        shortage = self.shortage_id
        if not shortage.requirement_id:
            raise UserError("Temporary relief requires a linked manning requirement.")
        if self.relief_crew_profile_id.rank_id != shortage.rank_id:
            raise UserError("The relief crew rank must match the shortage rank.")
        assignment = self.relief_assignment_id or self.env["sedar.crew.assignment"].create({
            "requirement_id": shortage.requirement_id.id,
            "crew_profile_id": self.relief_crew_profile_id.id,
            "state": "planned",
        })
        assignment.flush_recordset()
        if not assignment.is_eligible:
            if not self.relief_assignment_id:
                assignment.unlink()
            raise UserError("Selected relief crew is not eligible: %s" % assignment.eligibility_reason)
        self.write({
            "relief_assignment_id": assignment.id,
            "state": "completed",
            "completed_date": fields.Date.context_today(self),
        })
        shortage.action_resolve()

    def action_start(self):
        result = super().action_start()
        self._sedar_create_unavailability_from_action()
        return result

    def _sedar_create_unavailability_from_action(self):
        for action in self.filtered(lambda item: item.action_type in {"medical", "training"}):
            if action.unavailability_id:
                continue
            if not action.assigned_employee_id or not action.unavailability_start:
                continue
            profile = self.env["sedar.crew.profile"].search([
                ("employee_id", "=", action.assigned_employee_id.id)
            ], limit=1)
            if not profile:
                continue
            source = "medical" if action.action_type == "medical" else "training"
            action.unavailability_id = self.env["sedar.crew.unavailability"].create({
                "crew_profile_id": profile.id,
                "source": source,
                "shortage_id": action.shortage_id.id,
                "action_id": action.id,
                "date_start": action.unavailability_start,
                "date_end": action.unavailability_end,
                "state": "active",
                "reason": action.unavailability_reason or dict(action._fields["action_type"].selection).get(action.action_type),
                "notes": action.outcome,
            }).id

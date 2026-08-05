from odoo import api, fields, models
from odoo.exceptions import UserError


class SedarCrewAssignment(models.Model):
    _inherit = "sedar.crew.assignment"

    planned_start = fields.Datetime(related="order_id.requested_start", store=True)
    planned_end = fields.Datetime(related="order_id.requested_completion", store=True)
    scheduling_status = fields.Selection(
        [
            ("eligible", "Eligible"),
            ("blocked", "Blocked"),
            ("rejected", "Rejected"),
        ],
        compute="_compute_scheduling_status",
        store=True,
    )
    replacement_candidate_ids = fields.Many2many(
        "sedar.crew.profile",
        compute="_compute_replacement_candidates",
        string="Suggested Replacement Crew",
    )

    @api.depends("state", "is_eligible")
    def _compute_scheduling_status(self):
        for assignment in self:
            if assignment.state == "rejected":
                assignment.scheduling_status = "rejected"
            elif assignment.is_eligible:
                assignment.scheduling_status = "eligible"
            else:
                assignment.scheduling_status = "blocked"

    @api.depends(
        "crew_profile_id",
        "rank_id",
        "planned_start",
        "planned_end",
        "requirement_id.required_certificate_type_ids",
    )
    def _compute_replacement_candidates(self):
        profile_model = self.env["sedar.crew.profile"]
        assignment_model = self.env["sedar.crew.assignment"]
        for assignment in self:
            if not assignment.rank_id or not assignment.planned_start:
                assignment.replacement_candidate_ids = False
                continue
            candidates = profile_model.search([
                ("id", "!=", assignment.crew_profile_id.id),
                ("rank_id", "=", assignment.rank_id.id),
                ("active", "=", True),
                ("availability_status", "=", "available"),
            ])
            available = candidates.filtered(
                lambda profile: assignment._sedar_profile_satisfies_schedule(profile, assignment_model)
            )
            assignment.replacement_candidate_ids = available[:10]

    def _sedar_profile_satisfies_schedule(self, profile, assignment_model):
        self.ensure_one()
        start_date = fields.Date.to_date(self.planned_start)
        required_types = self.requirement_id.required_certificate_type_ids
        verified_types = profile.certificate_ids.filtered(
            lambda certificate: certificate.expiry_date >= start_date
            and certificate.sedar_verification_state == "verified"
        ).mapped("certificate_type_id")
        if required_types - verified_types:
            return False
        if profile.unavailability_ids.filtered(
            lambda item: item.state in {"planned", "active"} and item.overlaps_window(self.planned_start, self.planned_end)
        ):
            return False
        overlap_count = assignment_model.search_count([
            ("id", "!=", self.id),
            ("crew_profile_id", "=", profile.id),
            ("state", "in", ["planned", "confirmed"]),
            ("order_id.requested_start", "<", self.planned_end),
            ("order_id.requested_completion", ">", self.planned_start),
        ])
        return not overlap_count

    def action_confirm_assignment(self):
        for assignment in self:
            assignment.flush_recordset()
            if assignment.state == "rejected":
                raise UserError("Rejected crew assignments cannot be confirmed.")
            if not assignment.is_eligible:
                raise UserError("Resolve the scheduling blocker before confirming: %s" % assignment.eligibility_reason)
            assignment.state = "confirmed"
        self.mapped("order_id")._sync_automated_readiness()
        return True

    def action_reject_assignment(self):
        self.write({"state": "rejected"})
        self.mapped("order_id")._sync_automated_readiness()
        return True

    def write(self, vals):
        if vals.get("state") == "confirmed":
            for assignment in self:
                assignment.flush_recordset()
                if not assignment.is_eligible:
                    raise UserError("Resolve the scheduling blocker before confirming: %s" % assignment.eligibility_reason)
        result = super().write(vals)
        if {"crew_profile_id", "state"}.intersection(vals):
            self.mapped("order_id")._sync_automated_readiness()
        return result

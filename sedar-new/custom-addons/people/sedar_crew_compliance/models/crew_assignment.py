from odoo import api, fields, models


class SedarCrewAssignment(models.Model):
    _inherit = "sedar.crew.assignment"

    @api.depends(
        "crew_profile_id.rank_id",
        "crew_profile_id.availability_status",
        "crew_profile_id.active",
        "crew_profile_id.certificate_ids.certificate_type_id",
        "crew_profile_id.certificate_ids.expiry_date",
        "crew_profile_id.certificate_ids.sedar_verification_state",
        "requirement_id.required_certificate_type_ids",
        "order_id.requested_start",
        "order_id.requested_completion",
        "state",
    )
    def _compute_eligibility(self):
        for assignment in self:
            reasons = []
            profile = assignment.crew_profile_id
            requirement = assignment.requirement_id
            if not profile.active:
                reasons.append("Inactive crew profile")
            if profile.rank_id != requirement.rank_id:
                reasons.append("Incorrect rank")
            if profile.availability_status == "leave":
                reasons.append("Employee is on leave")
            elif profile.availability_status == "unavailable":
                reasons.append("Employee is unavailable")

            start_date = fields.Date.to_date(assignment.order_id.requested_start)
            verified_type_ids = profile.certificate_ids.filtered(
                lambda certificate: certificate.expiry_date >= start_date
                and certificate.sedar_verification_state == "verified"
            ).mapped("certificate_type_id").ids if start_date else []
            missing_types = requirement.required_certificate_type_ids.filtered(
                lambda cert_type: cert_type.id not in verified_type_ids
            )
            if missing_types:
                reasons.append("Missing, expired, or unverified: %s" % ", ".join(missing_types.mapped("name")))

            if assignment.state != "rejected" and assignment.order_id.requested_start:
                overlapping = self.search_count([
                    ("id", "!=", assignment.id),
                    ("crew_profile_id", "=", profile.id),
                    ("state", "in", ["planned", "confirmed"]),
                    ("order_id.requested_start", "<", assignment.order_id.requested_completion),
                    ("order_id.requested_completion", ">", assignment.order_id.requested_start),
                ])
                if overlapping:
                    reasons.append("Overlapping crew assignment")
            assignment.is_eligible = not reasons
            assignment.eligibility_reason = "; ".join(reasons) or "Eligible"

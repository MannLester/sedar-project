from odoo import api, fields, models


class SedarCrewOnboarding(models.Model):
    _inherit = "sedar.crew.onboarding"

    @api.depends(
        "crew_profile_id",
        "crew_profile_id.active",
        "crew_profile_id.rank_id",
        "crew_profile_id.home_tugboat_id",
        "crew_profile_id.certificate_ids.certificate_type_id",
        "crew_profile_id.certificate_ids.expiry_date",
        "crew_profile_id.certificate_ids.sedar_verification_state",
        "rank_id",
        "home_tugboat_id",
        "required_certificate_type_ids",
    )
    def _compute_deployment_status(self):
        today = fields.Date.context_today(self)
        for onboarding in self:
            reasons = []
            missing = self.env["sedar.crew.certificate.type"]
            profile = onboarding.crew_profile_id
            if not profile:
                reasons.append("Crew Profile not created")
            else:
                if not profile.active:
                    reasons.append("Crew Profile inactive")
                if profile.rank_id != onboarding.rank_id:
                    reasons.append("Crew Profile rank mismatch")
                if not profile.home_tugboat_id:
                    reasons.append("Home tugboat missing")
                verified_types = profile.certificate_ids.filtered(
                    lambda certificate: certificate.expiry_date >= today
                    and certificate.sedar_verification_state == "verified"
                ).mapped("certificate_type_id")
                missing = onboarding.required_certificate_type_ids - verified_types
                if missing:
                    reasons.append("Missing, expired, or unverified: %s" % ", ".join(missing.mapped("name")))
            onboarding.missing_certificate_type_ids = missing
            onboarding.deployment_eligible = not reasons
            onboarding.blocker_summary = "; ".join(reasons) or "Deployment eligible"

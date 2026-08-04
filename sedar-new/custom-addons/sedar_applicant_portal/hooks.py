from datetime import timedelta
import secrets

from odoo import fields


def post_init_hook(env):
    now = fields.Datetime.now()
    applicants = env["hr.applicant"].search([])
    for applicant in applicants:
        values = {}
        if not applicant.sedar_claim_token:
            values.update({
                "sedar_claim_token": secrets.token_urlsafe(32),
                "sedar_claim_expires_at": now + timedelta(days=2),
            })
        if not applicant.sedar_public_status:
            values.update({"sedar_public_status": "received", "sedar_status_updated_at": now})
        if values:
            applicant.write(values)
        if not applicant.sedar_portal_event_ids:
            applicant._create_portal_event("received", "Application Received", "Your application was received by SEDAR.")

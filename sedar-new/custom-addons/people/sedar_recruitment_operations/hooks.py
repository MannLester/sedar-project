from odoo import fields


def post_init_hook(env):
    applicants = env["hr.applicant"].search([])
    history_model = env["sedar.applicant.stage.history"]
    for applicant in applicants:
        if applicant.stage_id and not history_model.search_count([("applicant_id", "=", applicant.id)]):
            history_model.create({
                "applicant_id": applicant.id,
                "new_stage_id": applicant.stage_id.id,
                "changed_by": env.user.id,
                "changed_at": fields.Datetime.now(),
                "reason": "Stage history initialized during SEDAR Recruitment Operations installation.",
                "applicant_message": applicant.sedar_public_message,
            })

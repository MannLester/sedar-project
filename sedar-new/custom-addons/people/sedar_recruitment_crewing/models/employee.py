from odoo import fields, models


class SedarHrEmployeeCrewOnboarding(models.Model):
    _inherit = "hr.employee"

    sedar_crew_onboarding_ids = fields.One2many(
        "sedar.crew.onboarding",
        "employee_id",
        string="Marine Crew Onboarding",
        readonly=True,
    )

from odoo import models


class SedarApplicantCrewHandoff(models.Model):
    _inherit = "hr.applicant"

    def _sedar_apply_employee_onboarding_sources(self, employee, offer, request):
        result = super()._sedar_apply_employee_onboarding_sources(employee, offer, request)
        for applicant in self:
            if applicant.sedar_vacancy_id.crew_rank_id:
                self.env["sedar.crew.onboarding"].sudo()._sedar_get_or_create_from_employee(employee.sudo())
        return result

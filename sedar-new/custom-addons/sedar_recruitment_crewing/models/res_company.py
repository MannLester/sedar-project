from odoo import Command, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_ensure_crew_onboarding_demo(self):
        employee = self.env.ref("sedar_recruitment_demo.employee_converted_chief_engineer", raise_if_not_found=False)
        if not employee or not employee.sedar_source_vacancy_id.crew_rank_id:
            return True
        onboarding = self.env["sedar.crew.onboarding"]._sedar_get_or_create_from_employee(employee)
        if not onboarding:
            return True
        tug = self.env.ref("sedar_service_order_demo.tug_lakas", raise_if_not_found=False)
        if tug and not onboarding.home_tugboat_id:
            onboarding.home_tugboat_id = tug.id
        if onboarding.state == "draft":
            onboarding.state = "in_progress"
        if not onboarding.required_certificate_type_ids:
            onboarding.required_certificate_type_ids = [Command.set(self._sedar_default_demo_certificates().ids)]
        return True

    def _sedar_default_demo_certificates(self):
        xmlids = [
            "sedar_service_order_demo.certificate_type_stcw",
            "sedar_service_order_demo.certificate_type_sirb",
            "sedar_service_order_demo.certificate_type_med",
            "sedar_service_order_demo.certificate_type_dat",
            "sedar_service_order_demo.certificate_type_coc_e",
        ]
        records = self.env["sedar.crew.certificate.type"]
        for xmlid in xmlids:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                records |= record
        return records

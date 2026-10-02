from odoo import fields, http
from odoo.http import request


EMPLOYMENT_LABELS = {
    "permanent": "Permanent",
    "fixed_term": "Fixed-Term",
    "temporary": "Temporary Reliever",
}


class SedarCareersController(http.Controller):
    @http.route(
        "/sedar/api/v1/careers/jobs",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def jobs(self):
        vacancies = request.env["sedar.job.vacancy"].sudo().search(
            [
                ("state", "=", "open"),
                ("publication_state", "=", "published"),
                ("active", "=", True),
                ("remaining_openings", ">", 0),
            ],
            order="published_at desc, id desc",
        )
        vacancies = vacancies.filtered(lambda vacancy: vacancy.accepting_applications)
        return request.make_json_response({
            "version": 1,
            "jobs": [self._serialize(vacancy) for vacancy in vacancies],
        })

    @staticmethod
    def _serialize(vacancy):
        return {
            "slug": vacancy.public_slug,
            "apply_url": "/careers/apply/%s" % vacancy.public_slug,
            "title": vacancy.website_title,
            "department": vacancy.department_id.name,
            "location": vacancy.website_location_id.name,
            "employment_type": {
                "code": vacancy.employment_type,
                "label": EMPLOYMENT_LABELS.get(vacancy.employment_type, vacancy.employment_type),
            },
            "summary": vacancy.website_summary,
            "openings": vacancy.remaining_openings,
            "opening_date": fields.Date.to_string(vacancy.opening_date) if vacancy.opening_date else None,
            "application_deadline": fields.Date.to_string(vacancy.application_deadline) if vacancy.application_deadline else None,
        }

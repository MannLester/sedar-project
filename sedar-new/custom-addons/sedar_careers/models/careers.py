import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


def _slugify(value):
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


class SedarCareersLocation(models.Model):
    _name = "sedar.careers.location"
    _description = "SEDAR Careers Work Location"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)", "A Careers location with this name already exists."
    )


class SedarJobVacancy(models.Model):
    _inherit = "sedar.job.vacancy"

    website_location_id = fields.Many2one(
        "sedar.careers.location", string="Website Location", ondelete="restrict"
    )
    public_slug = fields.Char(readonly=True, copy=False, index=True)
    published_at = fields.Datetime(readonly=True, copy=False)
    published_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    publication_notes = fields.Text()
    website_visible = fields.Boolean(compute="_compute_website_visibility")
    accepting_applications = fields.Boolean(compute="_compute_website_visibility")

    _public_slug_unique = models.Constraint(
        "UNIQUE(public_slug)", "The public vacancy slug must be unique."
    )

    @api.depends("state", "publication_state", "active", "remaining_openings", "application_deadline")
    def _compute_website_visibility(self):
        today = fields.Date.context_today(self)
        for vacancy in self:
            accepting = (
                vacancy.state == "open"
                and vacancy.publication_state == "published"
                and vacancy.active
                and vacancy.remaining_openings > 0
                and (not vacancy.application_deadline or vacancy.application_deadline >= today)
            )
            vacancy.accepting_applications = accepting
            vacancy.website_visible = accepting

    def _make_public_slug(self):
        self.ensure_one()
        title = self.website_title or self.job_id.name or self.name
        location = self.website_location_id.name if self.website_location_id else ""
        base = _slugify("-".join(part for part in (title, location) if part)) or "vacancy"
        return "%s-%s" % (base, self.id)

    @api.model_create_multi
    def create(self, vals_list):
        vacancies = super().create(vals_list)
        for vacancy in vacancies:
            if not vacancy.public_slug:
                vacancy.public_slug = vacancy._make_public_slug()
        return vacancies

    def _validate_publication(self):
        for vacancy in self:
            missing = []
            if vacancy.state != "open":
                raise UserError("Only open vacancies can be published.")
            if vacancy.publication_state != "approved":
                raise UserError("Approve the vacancy for publication first.")
            if not vacancy.website_title:
                missing.append("Website Title")
            if not vacancy.website_summary:
                missing.append("Website Summary")
            if not vacancy.website_location_id:
                missing.append("Website Location")
            if not vacancy.responsibilities:
                missing.append("Responsibilities")
            if not vacancy.requirements:
                missing.append("Requirements")
            if vacancy.remaining_openings < 1:
                raise UserError("A vacancy must have at least one remaining opening.")
            if vacancy.application_deadline and vacancy.application_deadline < fields.Date.context_today(vacancy):
                raise UserError("The application deadline must not be in the past.")
            if missing:
                raise ValidationError("Complete these fields before publishing: %s." % ", ".join(missing))

    def action_publish(self):
        self._ensure_hr_manager()
        self._validate_publication()
        for vacancy in self:
            vacancy.write({
                "publication_state": "published",
                "published_at": fields.Datetime.now(),
                "published_by_id": self.env.user.id,
            })
            vacancy.message_post(body="Vacancy published on the SEDAR Careers website.")
        return True

    def action_remove_from_website(self):
        self._ensure_hr_manager()
        self.write({"publication_state": "approved"})
        self.message_post(body="Vacancy removed from the SEDAR Careers website.")
        return True

    def _ensure_hr_manager(self):
        if not self.env.user.has_group("sedar_manpower_planning.group_hr_manager"):
            raise UserError("Only an HR Manager can manage Careers publication.")

    def action_close(self):
        result = super().action_close()
        self.write({"published_at": False, "published_by_id": False})
        return result

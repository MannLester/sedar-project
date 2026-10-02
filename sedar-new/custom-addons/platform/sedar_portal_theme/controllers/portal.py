from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website.controllers.main import Website


class SedarWebsiteRoot(Website):
    @route()
    def index(self, **kw):
        return request.redirect("/web/login")


class SedarPortalHome(CustomerPortal):
    @route()
    def home(self, **kw):
        partner = request.env.user.partner_id

        has_applications = request.env["hr.applicant"].sudo().search_count([
            ("sedar_portal_partner_id", "=", partner.id),
            ("active", "=", True),
        ])
        if has_applications:
            return request.redirect("/my/sedar")

        commercial_partner = partner.commercial_partner_id
        has_client_records = (
            commercial_partner.sedar_is_customer_account
            or request.env["sedar.marine.service.order"].sudo().search_count([
                ("client_id", "=", commercial_partner.id),
                ("company_id", "in", request.env.companies.ids),
            ])
            or request.env["sedar.client.vessel"].sudo().search_count([
                ("owner_id", "=", commercial_partner.id),
                ("active", "=", True),
            ])
        )
        if has_client_records:
            return request.redirect("/my/sedar/orders")

        return super().home(**kw)

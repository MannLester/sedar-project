import base64
from datetime import datetime

import pytz
from werkzeug.exceptions import NotFound

from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal


class SedarMarineCustomerPortal(CustomerPortal):

    def _commercial_partner(self):
        return request.env.user.partner_id.commercial_partner_id

    def _order_domain(self):
        return [("client_id", "=", self._commercial_partner().id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "sedar_order_count" in counters:
            values["sedar_order_count"] = request.env["sedar.marine.service.order"].sudo().search_count(
                self._order_domain()
            )
        return values

    def _new_order_values(self, **extra):
        partner = self._commercial_partner()
        values = {
            "page_name": "sedar_order_new",
            "service_types": request.env["sedar.marine.service.type"].sudo().search([("active", "=", True)]),
            "ports": request.env["sedar.marine.port"].sudo().search([("active", "=", True)]),
            "berths": request.env["sedar.marine.berth"].sudo().search([("active", "=", True)]),
            "tug_classes": request.env["sedar.tug.class"].sudo().search([("active", "=", True)]),
            "vessels": request.env["sedar.client.vessel"].sudo().search([
                ("owner_id", "=", partner.id), ("active", "=", True)
            ]),
            "errors": [],
            "form": {},
        }
        values.update(extra)
        return values

    @route(["/my/sedar/orders"], type="http", auth="user", website=True, readonly=True)
    def portal_orders(self, **kwargs):
        orders = request.env["sedar.marine.service.order"].sudo().search(
            self._order_domain(), order="requested_start desc, id desc"
        )
        values = self._prepare_portal_layout_values()
        values.update({"page_name": "sedar_orders", "orders": orders})
        return request.render("sedar_marine_operations.portal_my_sedar_orders", values)

    @route(["/my/sedar/orders/new"], type="http", auth="user", website=True)
    def portal_order_new(self, **kwargs):
        return request.render(
            "sedar_marine_operations.portal_sedar_order_form",
            self._new_order_values(),
        )

    def _get_record(self, model_name, value, domain=None):
        try:
            record_id = int(value or 0)
        except (TypeError, ValueError):
            return request.env[model_name]
        model = request.env[model_name].sudo()
        record = model.browse(record_id).exists()
        if record and domain and not model.search_count([("id", "=", record.id), *domain]):
            return request.env[model_name]
        return record

    def _parse_requested_start(self, value, port):
        if not port:
            return False
        try:
            local_start = datetime.fromisoformat(value)
            timezone = pytz.timezone(port.timezone or request.env.user.tz or "Asia/Manila")
            return timezone.localize(local_start).astimezone(pytz.UTC).replace(tzinfo=None)
        except (TypeError, ValueError, pytz.UnknownTimeZoneError):
            return False

    def _parse_resources(self, post, errors):
        try:
            number_of_tugs = int(post.get("number_of_tugs") or 1)
            duration = float(post.get("estimated_duration_hours") or 1)
            if number_of_tugs < 1 or duration <= 0:
                raise ValueError
            return number_of_tugs, duration
        except ValueError:
            errors.append("Number of tugs and estimated duration must be greater than zero.")
            return 1, 1.0

    def _uploaded_file_values(self, uploaded):
        if uploaded and getattr(uploaded, "filename", False):
            return base64.b64encode(uploaded.read()), uploaded.filename
        return False, False

    @route(["/my/sedar/orders/create"], type="http", auth="user", website=True, methods=["POST"])
    def portal_order_create(self, **post):
        errors = []
        partner = self._commercial_partner()
        service_type = self._get_record("sedar.marine.service.type", post.get("service_type_id"), [("active", "=", True)])
        port = self._get_record("sedar.marine.port", post.get("port_id"), [("active", "=", True)])
        tug_class = self._get_record("sedar.tug.class", post.get("tug_class_id"), [("active", "=", True)])
        vessel = self._get_record("sedar.client.vessel", post.get("assisted_vessel_id"), [("owner_id", "=", partner.id)])

        if not service_type:
            errors.append("Select a valid service type.")
        if not port:
            errors.append("Select a valid port or operating area.")
        new_vessel_name = (post.get("new_vessel_name") or "").strip()
        if not vessel and not new_vessel_name:
            errors.append("Select an assisted vessel or enter a new vessel name.")
        if not (post.get("scope_of_work") or "").strip():
            errors.append("Enter the scope of work.")
        requested_start = self._parse_requested_start(post.get("requested_start"), port)
        if not requested_start:
            errors.append("Enter a valid requested start date and time.")
        number_of_tugs, duration = self._parse_resources(post, errors)

        if errors:
            return request.render(
                "sedar_marine_operations.portal_sedar_order_form",
                self._new_order_values(errors=errors, form=post),
            )

        if not vessel:
            vessel = request.env["sedar.client.vessel"].sudo().create({
                "name": new_vessel_name,
                "owner_id": partner.id,
                "imo_number": (post.get("new_vessel_imo") or "").strip(),
            })

        origin = self._get_record("sedar.marine.berth", post.get("origin_berth_id"), [("port_id", "=", port.id)])
        destination = self._get_record("sedar.marine.berth", post.get("destination_berth_id"), [("port_id", "=", port.id)])
        file_data, filename = self._uploaded_file_values(post.get("supporting_document"))

        order = request.env["sedar.marine.service.order"].sudo().create({
            "client_id": partner.id,
            "contact_id": request.env.user.partner_id.id,
            "request_channel": "portal",
            "client_reference": (post.get("client_reference") or "").strip(),
            "priority": post.get("priority") if post.get("priority") in {"normal", "urgent", "emergency"} else "normal",
            "assisted_vessel_id": vessel.id,
            "assisted_vessel_name": vessel.name,
            "service_type_id": service_type.id,
            "number_of_tugs": number_of_tugs,
            "tug_class_id": tug_class.id if tug_class else False,
            "scope_of_work": post.get("scope_of_work").strip(),
            "special_instructions": (post.get("special_instructions") or "").strip(),
            "port_id": port.id,
            "origin_berth_id": origin.id if origin else False,
            "destination_berth_id": destination.id if destination else False,
            "requested_start": requested_start,
            "estimated_duration_hours": duration,
            "hazardous_cargo": post.get("hazardous_cargo") == "on",
            "cargo_description": (post.get("cargo_description") or "").strip(),
            "permit_required": post.get("permit_required") == "on",
            "safety_requirements": (post.get("safety_requirements") or "").strip(),
            "supporting_document": file_data,
            "supporting_document_filename": filename,
            "state": "submitted",
        })
        return request.redirect(order.access_url)

    @route(["/my/sedar/orders/<int:order_id>"], type="http", auth="user", website=True, readonly=True)
    def portal_order_detail(self, order_id, **kwargs):
        order = request.env["sedar.marine.service.order"].sudo().search([
            ("id", "=", order_id), *self._order_domain()
        ], limit=1)
        if not order:
            raise NotFound()
        values = self._prepare_portal_layout_values()
        values.update({"page_name": "sedar_order", "order": order})
        return request.render("sedar_marine_operations.portal_sedar_order_detail", values)

    @route(["/my/sedar/orders/<int:order_id>/confirm"], type="http", auth="user", website=True, methods=["POST"])
    def portal_order_confirm(self, order_id, **post):
        order = request.env["sedar.marine.service.order"].sudo().search([
            ("id", "=", order_id), ("state", "=", "quoted"), *self._order_domain()
        ], limit=1)
        if not order:
            raise NotFound()
        order.action_confirm()
        return request.redirect(order.access_url)

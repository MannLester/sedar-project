from odoo.http import request, route
from odoo.addons.sedar_marine_operations.controllers.portal import SedarMarineCustomerPortal


class SedarMarineDispatchPortal(SedarMarineCustomerPortal):

    def _operation_domain(self, order):
        return [
            ("order_id", "=", order.id),
            ("company_id", "in", self._allowed_company_ids()),
        ]

    def _client_log_domain(self, operation):
        return [
            ("operation_id", "=", operation.id),
            ("company_id", "in", self._allowed_company_ids()),
            ("client_visible", "=", True),
        ]

    def _client_delay_domain(self, operation):
        return [
            ("operation_id", "=", operation.id),
            ("company_id", "in", self._allowed_company_ids()),
            ("client_visible", "=", True),
        ]

    @route(["/my/sedar/orders/<int:order_id>"], type="http", auth="user", website=True, readonly=True)
    def portal_order_detail(self, order_id, **kwargs):
        order = self._get_portal_order(order_id)
        if not order:
            from werkzeug.exceptions import NotFound
            raise NotFound()
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "sedar_order",
            "order": order,
            "operation": request.env["sedar.marine.operation"].sudo().search(
                self._operation_domain(order), limit=1
            ),
        })
        operation = values["operation"]
        values["client_logs"] = (
            request.env["sedar.marine.operation.log"].sudo().search(
                self._client_log_domain(operation)
            )
            if operation
            else request.env["sedar.marine.operation.log"]
        )
        values["client_delays"] = (
            request.env["sedar.marine.operation.delay"].sudo().search(
                self._client_delay_domain(operation)
            )
            if operation
            else request.env["sedar.marine.operation.delay"]
        )
        return request.render("sedar_marine_dispatch.portal_sedar_order_detail_dispatch", values)

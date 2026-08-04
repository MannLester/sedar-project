from odoo.http import request, route
from odoo.addons.sedar_marine_operations.controllers.portal import SedarMarineCustomerPortal


class SedarMarineDispatchPortal(SedarMarineCustomerPortal):

    @route(["/my/sedar/orders/<int:order_id>"], type="http", auth="user", website=True, readonly=True)
    def portal_order_detail(self, order_id, **kwargs):
        order = request.env["sedar.marine.service.order"].sudo().search([
            ("id", "=", order_id), *self._order_domain()
        ], limit=1)
        if not order:
            from werkzeug.exceptions import NotFound
            raise NotFound()
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "sedar_order",
            "order": order,
            "operation": order.operation_ids[:1],
        })
        operation = values["operation"]
        values["client_logs"] = operation.log_ids.filtered(lambda line: line.client_visible) if operation else request.env["sedar.marine.operation.log"]
        values["client_delays"] = operation.delay_ids.filtered(lambda delay: delay.client_visible) if operation else request.env["sedar.marine.operation.delay"]
        return request.render("sedar_marine_dispatch.portal_sedar_order_detail_dispatch", values)

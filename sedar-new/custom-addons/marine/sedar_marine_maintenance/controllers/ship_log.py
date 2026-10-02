from odoo import http
from odoo.http import request


class ShipLogController(http.Controller):
    """JSON endpoints for the offline ship log page (static/ship_log); all rules live in sedar.ship.log.entry."""

    @http.route("/sedar/ship-log/snapshot", type="jsonrpc", auth="user")
    def snapshot(self):
        return request.env["sedar.ship.log.entry"]._sedar_snapshot()

    @http.route("/sedar/ship-log/sync", type="jsonrpc", auth="user")
    def sync(self, items):
        return request.env["sedar.ship.log.entry"]._sedar_sync(items)

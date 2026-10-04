from odoo import http
from odoo.http import request


class ShipLogController(http.Controller):
    """JSON endpoints for the offline ship log (static/ship_log) and Engine Room (static/engine_room) pages; the rules live in the models."""

    @http.route("/sedar/ship-log/snapshot", type="jsonrpc", auth="user")
    def snapshot(self):
        return request.env["sedar.ship.log.entry"]._sedar_snapshot()

    @http.route("/sedar/ship-log/sync", type="jsonrpc", auth="user")
    def sync(self, items):
        return request.env["sedar.ship.log.entry"]._sedar_sync(items)

    @http.route("/sedar/engine-room/snapshot", type="jsonrpc", auth="user")
    def engine_room_snapshot(self):
        return request.env["sedar.daily.engine.report"]._sedar_engine_room_snapshot()

    @http.route("/sedar/engine-room/review", type="jsonrpc", auth="user")
    def engine_room_review(self, item):
        return request.env["sedar.daily.engine.report"]._sedar_review(item)

    @http.route("/sedar/engine-room/embed.js", type="http", auth="user")
    def engine_room_bundle(self):
        return http.Stream.from_path("sedar_marine_maintenance/static/engine_room/embed.js").get_response(max_age=0)

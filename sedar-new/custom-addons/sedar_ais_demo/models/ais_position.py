from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError


MAP_BOUNDS = {
    "min_lat": 13.69,
    "max_lat": 13.84,
    "min_lon": 120.88,
    "max_lon": 121.15,
}

SIMULATION_ROUTES = {
    "SEDAR-TUG-001": [
        (13.7560, 121.0040, "Batangas Anchorage", 6.8, 112),
        (13.7480, 121.0210, "Batangas Bay Traffic Lane", 7.4, 118),
        (13.7380, 121.0390, "Approaching SEDAR Base", 5.1, 132),
        (13.7280, 121.0540, "SEDAR Base Approach", 3.2, 145),
    ],
    "SEDAR-TUG-002": [
        (13.7350, 121.0470, "SEDAR Base", 0.0, 30),
        (13.7410, 121.0360, "Batangas Inner Harbor", 4.5, 306),
        (13.7490, 121.0240, "Batangas Bay Traffic Lane", 6.2, 310),
        (13.7560, 121.0130, "North Anchorage Approach", 5.8, 318),
    ],
    "SEDAR-TUG-003": [
        (13.7160, 121.0280, "South Batangas Bay", 8.2, 42),
        (13.7270, 121.0390, "South Harbor Approach", 7.5, 38),
        (13.7400, 121.0480, "SEDAR Base Approach", 4.8, 24),
        (13.7510, 121.0530, "Batangas Inner Harbor", 3.7, 12),
    ],
    "SEDAR-TUG-004": [
        (13.7440, 121.0710, "Demo Batangas Repair Yard", 0.0, 90),
    ],
    "SEDAR-TUG-005": [
        (13.7830, 120.9590, "West Batangas Anchorage", 5.6, 104),
        (13.7770, 120.9810, "Batangas Bay West Lane", 6.4, 110),
        (13.7690, 121.0020, "Northwest Harbor Approach", 6.9, 116),
        (13.7580, 121.0190, "Batangas Bay Traffic Lane", 5.3, 128),
    ],
}


class SedarTugboat(models.Model):
    _inherit = "sedar.tugboat"

    ais_position_ids = fields.One2many(
        "sedar.ais.position", "tugboat_id", string="Simulated AIS Position"
    )


class SedarAisPosition(models.Model):
    _name = "sedar.ais.position"
    _description = "Simulated Tugboat AIS Position"
    _inherit = ["mail.thread"]
    _order = "tugboat_id"

    tugboat_id = fields.Many2one(
        "sedar.tugboat", required=True, ondelete="cascade", index=True, tracking=True
    )
    latitude = fields.Float(required=True, digits=(10, 6), tracking=True)
    longitude = fields.Float(required=True, digits=(10, 6), tracking=True)
    previous_latitude = fields.Float(digits=(10, 6))
    previous_longitude = fields.Float(digits=(10, 6))
    speed_knots = fields.Float(string="Speed (kn)", tracking=True)
    course_degrees = fields.Float(string="Course (°)", tracking=True)
    navigation_status = fields.Selection(
        [
            ("underway", "Underway"),
            ("assisting", "Assisting Vessel"),
            ("standby", "Standby"),
            ("berthed", "Berthed"),
            ("dry_dock", "Dry Dock"),
            ("maintenance", "Maintenance Hold"),
            ("offline", "Signal Offline"),
        ],
        required=True,
        default="standby",
        tracking=True,
    )
    location_label = fields.Char(required=True)
    destination = fields.Char()
    eta = fields.Datetime(string="ETA")
    last_reported_at = fields.Datetime(required=True, default=fields.Datetime.now)
    signal_quality = fields.Selection(
        [("strong", "Strong"), ("fair", "Fair"), ("weak", "Weak")],
        required=True,
        default="strong",
    )
    route_index = fields.Integer(default=0)
    simulated = fields.Boolean(default=True, readonly=True)

    _tugboat_unique = models.Constraint(
        "UNIQUE(tugboat_id)", "Each tugboat can have only one current simulated AIS position."
    )

    @api.constrains("latitude", "longitude", "course_degrees", "speed_knots")
    def _check_navigation_values(self):
        for position in self:
            if not -90 <= position.latitude <= 90:
                raise ValidationError("Latitude must be between -90 and 90 degrees.")
            if not -180 <= position.longitude <= 180:
                raise ValidationError("Longitude must be between -180 and 180 degrees.")
            if not 0 <= position.course_degrees < 360:
                raise ValidationError("Course must be between 0 and 359 degrees.")
            if position.speed_knots < 0:
                raise ValidationError("Speed cannot be negative.")

    @api.model
    def _map_coordinates(self, latitude, longitude):
        x = (longitude - MAP_BOUNDS["min_lon"]) / (
            MAP_BOUNDS["max_lon"] - MAP_BOUNDS["min_lon"]
        ) * 100
        y = (MAP_BOUNDS["max_lat"] - latitude) / (
            MAP_BOUNDS["max_lat"] - MAP_BOUNDS["min_lat"]
        ) * 100
        return max(3, min(x, 97)), max(4, min(y, 96))

    @api.model
    def _check_dashboard_access(self):
        if not self.env.su and not self.env.user.has_group(
            "sedar_ais_demo.group_sedar_ais_user"
        ):
            raise AccessError("You do not have access to simulated AIS fleet monitoring.")

    @api.model
    def _selection_label(self, record, field_name, value):
        return dict(record._fields[field_name].selection).get(value, value or "")

    @api.model
    def _crew_values(self, crew):
        return [
            {
                "id": profile.id,
                "name": profile.employee_id.name,
                "rank": profile.rank_id.name,
                "availability": profile.availability_status,
            }
            for profile in crew.sorted(lambda item: (item.rank_id.sequence, item.employee_id.name))
        ]

    @api.model
    def _dashboard_crew(self, dashboard, tugs, assignments):
        assignment_by_tug = {}
        for assignment in assignments:
            assignment_by_tug.setdefault(assignment.tugboat_id.id, assignment)
        current_crew = defaultdict(lambda: dashboard["sedar.crew.profile"])
        crew_assignments = dashboard["sedar.crew.assignment"].search([
            ("tug_assignment_id", "in", assignments.ids), ("state", "!=", "rejected"),
        ])
        for crew_assignment in crew_assignments:
            current_crew[crew_assignment.tug_assignment_id.id] |= crew_assignment.crew_profile_id
        home_crew = defaultdict(lambda: dashboard["sedar.crew.profile"])
        for profile in dashboard["sedar.crew.profile"].search([
            ("home_tugboat_id", "in", tugs.ids), ("active", "=", True),
        ]):
            home_crew[profile.home_tugboat_id.id] |= profile
        result = {}
        for tug in tugs:
            assignment = assignment_by_tug.get(tug.id)
            crew = current_crew[assignment.id] if assignment else False
            result[tug.id] = (
                assignment,
                "Current operation" if crew else "Home crew roster",
                self._crew_values(crew or home_crew[tug.id]),
            )
        return result

    @api.model
    def _equipment_summaries(self, dashboard, tugs):
        equipment_by_tug = defaultdict(list)
        equipment = dashboard["maintenance.equipment"].search([
            ("company_id", "=", self.env.company.id),
            ("sedar_tugboat_id", "in", tugs.ids),
            ("active", "=", True),
        ], order="sedar_tugboat_id, name, id")
        active_request_ids = defaultdict(set)
        requests = dashboard["sedar.purchase.request"].search([
            ("company_id", "=", self.env.company.id),
            ("equipment_id", "in", equipment.ids),
            ("state", "not in", ["rejected", "cancelled"]),
        ])
        for request in requests:
            if self._request_has_active_procurement(request):
                active_request_ids[request.equipment_id.id].add(request.id)
        for item in equipment:
            current = item.sedar_current_running_hour_reading_id
            equipment_by_tug[item.sedar_tugboat_id.id].append({
                "id": item.id,
                "name": item.name,
                "system": item.sedar_system,
                "system_label": self._selection_label(item, "sedar_system", item.sedar_system),
                "criticality": item.sedar_criticality,
                "criticality_label": self._selection_label(
                    item, "sedar_criticality", item.sedar_criticality
                ),
                "maintenance_state": item.sedar_service_due_state,
                "maintenance_state_label": self._selection_label(
                    item, "sedar_service_due_state", item.sedar_service_due_state
                ),
                "running_hours": item.sedar_current_running_hours,
                "reading_at": fields.Datetime.to_string(current.reading_at) if current else False,
                "next_service_due": item.sedar_next_service_hours or False,
                "active_procurement_count": len(active_request_ids[item.id]),
            })
        return equipment_by_tug

    @api.model
    def _request_has_active_procurement(self, request):
        return any(self._line_is_active(line) for line in request.line_ids)

    @api.model
    def _line_orders(self, line):
        return line.award_history_ids.mapped("purchase_order_line_id.order_id")

    @api.model
    def _line_is_active(self, line):
        if line.line_state != "active" or line.request_id.state in {"rejected", "cancelled"}:
            return False
        terminal_states = {"purchase", "done", "cancel"}
        return not any(order.state in terminal_states for order in self._line_orders(line))

    @api.model
    def get_dashboard_data(self):
        self._check_dashboard_access()
        can_advance = self.env.su or self.env.user.has_group("sedar_ais_demo.group_sedar_ais_manager")
        dashboard = self.env(su=True)
        company_id = self.env.company.id
        tugs = dashboard["sedar.tugboat"].search([
            ("active", "=", True), ("company_id", "=", company_id),
        ], order="name")
        positions = {
            item.tugboat_id.id: item for item in dashboard["sedar.ais.position"].search([
                ("tugboat_id", "in", tugs.ids),
            ])
        }
        drydocks = dashboard["sedar.drydock.plan"].search([
            ("company_id", "=", company_id), ("tugboat_id", "in", tugs.ids),
            ("state", "in", ["planned", "in_progress"]),
        ], order="planned_start desc, id desc")
        drydock_by_tug = {}
        for drydock in drydocks:
            drydock_by_tug.setdefault(drydock.tugboat_id.id, drydock)
        blocker_count = defaultdict(int)
        blockers = dashboard["maintenance.request"].search([
            ("company_id", "=", company_id), ("sedar_tugboat_id", "in", tugs.ids),
            ("sedar_blocks_tug_readiness", "=", True),
        ])
        for blocker in blockers:
            blocker_count[blocker.sedar_tugboat_id.id] += 1
        assignments = dashboard["sedar.tug.assignment"].search([
            ("company_id", "=", company_id), ("tugboat_id", "in", tugs.ids),
            ("state", "!=", "cancelled"),
            ("order_id.state", "in", ["ready", "dispatched", "in_progress"]),
        ], order="planned_start desc, id desc")
        crew_by_tug = self._dashboard_crew(dashboard, tugs, assignments)
        equipment_by_tug = self._equipment_summaries(dashboard, tugs)
        payload = []
        now = fields.Datetime.now()
        for tug in tugs:
            position = positions.get(tug.id)
            if not position:
                continue
            drydock = drydock_by_tug.get(tug.id)
            blockers = blocker_count[tug.id]
            assignment, crew_source, crew = crew_by_tug[tug.id]
            operation = assignment.order_id.operation_ids[:1] if assignment else False
            x, y = self._map_coordinates(position.latitude, position.longitude)
            px, py = self._map_coordinates(
                position.previous_latitude or position.latitude,
                position.previous_longitude or position.longitude,
            )
            effective_status = position.navigation_status
            if drydock:
                effective_status = "dry_dock"
            elif blockers:
                effective_status = "maintenance"
            payload.append({
                "id": tug.id,
                "position_id": position.id,
                "name": tug.name,
                "registration": tug.registration_number,
                "call_sign": tug.call_sign or "—",
                "mmsi": tug.mmsi or "—",
                "tug_class": tug.tug_class_id.name,
                "bollard_pull": tug.bollard_pull,
                "availability": tug.availability_status,
                "status": effective_status,
                "status_label": dict(position._fields["navigation_status"].selection).get(effective_status, effective_status),
                "latitude": position.latitude,
                "longitude": position.longitude,
                "x": round(x, 2),
                "y": round(y, 2),
                "previous_x": round(px, 2),
                "previous_y": round(py, 2),
                "speed": position.speed_knots,
                "course": position.course_degrees,
                "location": position.location_label,
                "destination": position.destination or "No active destination",
                "eta": fields.Datetime.to_string(position.eta) if position.eta else False,
                "last_reported": fields.Datetime.to_string(position.last_reported_at),
                "signal": position.signal_quality,
                "crew": crew,
                "crew_source": crew_source,
                "operation": operation.display_name if operation else False,
                "service_order": assignment.order_id.display_name if assignment else False,
                "drydock": {
                    "name": drydock.name,
                    "yard": drydock.yard_name,
                    "state": drydock.state,
                    "planned_end": fields.Datetime.to_string(drydock.planned_end),
                } if drydock else False,
                "maintenance_blockers": blockers,
                "equipment": equipment_by_tug[tug.id],
            })
        return {
            "simulation": True,
            "title": "Batangas Bay Fleet Monitoring",
            "generated_at": fields.Datetime.to_string(now),
            "can_advance": can_advance,
            "bounds": MAP_BOUNDS,
            "fleet": payload,
        }

    @api.model
    def _commercial_access(self):
        if self.env.su:
            return True
        user = self.env.user
        return bool(
            self.env.company.sedar_procurement_inventory_officer_id == user
            and user.active
            and not user.share
            and self.env.company in user.company_ids
            and user.has_group("sedar_marine_inventory.group_marine_inventory_manager")
        )

    @api.model
    def _equipment_for_detail(self, equipment_id):
        self._check_dashboard_access()
        if not isinstance(equipment_id, int) or isinstance(equipment_id, bool):
            raise AccessError("The selected Equipment is not available on this fleet display.")
        equipment = self.env["maintenance.equipment"].sudo().search([
            ("id", "=", equipment_id),
            ("active", "=", True),
            ("company_id", "=", self.env.company.id),
            ("sedar_tugboat_id.active", "=", True),
            ("sedar_tugboat_id.company_id", "=", self.env.company.id),
            ("sedar_tugboat_id.ais_position_ids", "!=", False),
        ], limit=1)
        if not equipment:
            raise AccessError("The selected Equipment is not available on this fleet display.")
        return equipment

    @api.model
    def _common_procurement_row(self, line):
        request = line.request_id
        orders = self._line_orders(line)
        return {
            "line_id": line.id,
            "request_id": request.id,
            "request_name": request.name,
            "product_id": line.product_id.id,
            "product_name": line.product_id.display_name,
            "progress": request.procurement_progress,
            "progress_label": self._selection_label(
                request, "procurement_progress", request.procurement_progress
            ),
            "bid_count": len(line.bid_line_ids),
            "order_count": len(orders),
        }

    @api.model
    def _safe_bid_attachment(self, bid):
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", bid._name), ("res_id", "=", bid.id),
            ("res_field", "=", "quotation_file"),
        ], limit=1)
        if not attachment:
            return False
        try:
            attachment.check_access("read")
        except AccessError:
            return False
        return {
            "id": attachment.id,
            "name": bid.quotation_filename or attachment.name,
            "mimetype": attachment.mimetype,
            "action": {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}?download=true",
                "target": "self",
            },
        }

    @api.model
    def _commercial_bid_values(self, bid_line):
        bid = bid_line.bid_id
        values = {
            "bid_name": bid.name,
            "bidder_name": bid.bidder_id.display_name,
            "state": bid.state,
            "state_label": self._selection_label(bid, "state", bid.state),
            "quantity": bid_line.quantity,
            "uom": bid_line.product_uom_id.name,
            "unit_price": bid_line.unit_price,
            "subtotal": bid_line.subtotal,
            "total_amount": bid.total_amount,
            "currency": bid.currency_id.name,
            "received_date": fields.Date.to_string(bid.received_date),
            "validity_date": fields.Date.to_string(bid.validity_date),
            "promised_delivery_date": fields.Date.to_string(bid.promised_delivery_date),
            "delivery_terms": bid.delivery_terms or False,
            "availability_notes": bid.availability_notes or False,
            "payment_terms": bid.payment_terms or False,
            "warranty_notes": bid.warranty_notes or False,
            "commercial_notes": bid.commercial_notes or False,
            "line_promised_delivery_date": fields.Date.to_string(
                bid_line.promised_delivery_date
            ),
            "line_delivery_terms": bid_line.delivery_terms or False,
            "line_availability_notes": bid_line.availability_note or False,
            "line_notes": bid_line.notes or False,
        }
        attachment = self._safe_bid_attachment(bid)
        if attachment:
            values["attachment"] = attachment
        return values

    @api.model
    def _commercial_procurement(self, line):
        bids = [
            self._commercial_bid_values(bid_line)
            for bid_line in line.bid_line_ids
        ]
        award = line.current_award_id
        award_values = False
        if award:
            award_values = {
                "bidder_name": award.bidder_id.display_name,
                "state": award.state,
                "state_label": self._selection_label(award, "state", award.state),
                "quantity": award.quantity,
                "unit_price": award.unit_price,
                "currency": award.currency_id.name,
                "reason": award.award_reason,
            }
        orders = [{
            "id": order.id,
            "name": order.name,
            "state": order.state,
            "state_label": self._selection_label(order, "state", order.state),
            "supplier_name": order.partner_id.display_name,
            "amount_total": order.amount_total,
            "currency": order.currency_id.name,
        } for order in self._line_orders(line)]
        return {"bids": bids, "award": award_values, "orders": orders}

    @api.model
    def get_equipment_procurement_detail(self, equipment_id):
        equipment = self._equipment_for_detail(equipment_id)
        commercial_access = self._commercial_access()
        requests = self.env["sedar.purchase.request"].sudo().search([
            ("company_id", "=", self.env.company.id),
            ("equipment_id", "=", equipment.id),
        ], order="required_date desc, id desc")
        active, history = [], []
        for line in requests.mapped("line_ids"):
            values = self._common_procurement_row(line)
            is_active = self._line_is_active(line)
            if not is_active:
                outcome = "cancelled" if (
                    line.line_state == "cancelled"
                    or line.request_id.state in {"rejected", "cancelled"}
                    or any(order.state == "cancel" for order in self._line_orders(line))
                ) else "ordered"
                values.update({"outcome": outcome, "outcome_label": outcome.title()})
            if commercial_access:
                values["commercial"] = self._commercial_procurement(line)
            (active if is_active else history).append(values)
        return {
            "equipment_id": equipment.id,
            "access": "full" if commercial_access else "limited",
            "active_procurement": active,
            "procurement_history": history,
        }

    @api.model
    def action_advance_simulation(self):
        if not self.env.user.has_group("sedar_ais_demo.group_sedar_ais_manager") and not self.env.su:
            raise AccessError("Only an AIS Simulation Manager may advance the demonstration feed.")
        for position in self.sudo().search([]):
            route = SIMULATION_ROUTES.get(position.tugboat_id.registration_number, [])
            if len(route) <= 1 or position.navigation_status in {"dry_dock", "maintenance", "offline"}:
                position.last_reported_at = fields.Datetime.now()
                continue
            next_index = (position.route_index + 1) % len(route)
            latitude, longitude, label, speed, course = route[next_index]
            position.write({
                "previous_latitude": position.latitude,
                "previous_longitude": position.longitude,
                "latitude": latitude,
                "longitude": longitude,
                "location_label": label,
                "speed_knots": speed,
                "course_degrees": course,
                "navigation_status": "underway" if speed else "berthed",
                "route_index": next_index,
                "last_reported_at": fields.Datetime.now(),
            })
        return self.get_dashboard_data()


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_ensure_ais_demo(self):
        env = self.env
        manager_group = env.ref("sedar_ais_demo.group_sedar_ais_manager")
        user = env.ref("sedar_ais_demo.user_ais_demo", raise_if_not_found=False)
        if not user:
            user = env["res.users"].create({
                "name": "Demo Fleet Monitoring Officer",
                "login": "ais@sedar.demo",
                "password": "aisdemo",
                "company_id": env.company.id,
                "company_ids": [Command.set([env.company.id])],
                "group_ids": [Command.set([manager_group.id])],
            })
            env["ir.model.data"].create({
                "module": "sedar_ais_demo", "name": "user_ais_demo", "model": "res.users",
                "res_id": user.id, "noupdate": True,
            })
        for tug in env["sedar.tugboat"].search([("active", "=", True)]):
            route = SIMULATION_ROUTES.get(tug.registration_number)
            if not route:
                continue
            latitude, longitude, label, speed, course = route[0]
            drydock = env["sedar.drydock.plan"].search([
                ("tugboat_id", "=", tug.id), ("state", "in", ["planned", "in_progress"]),
            ], limit=1)
            values = {
                "latitude": latitude,
                "longitude": longitude,
                "previous_latitude": latitude,
                "previous_longitude": longitude,
                "speed_knots": 0 if drydock else speed,
                "course_degrees": course,
                "navigation_status": "dry_dock" if drydock else ("underway" if speed else "berthed"),
                "location_label": drydock.yard_name if drydock else label,
                "destination": "SEDAR Base" if speed else False,
                "last_reported_at": fields.Datetime.now(),
                "signal_quality": "strong",
                "route_index": 0,
            }
            position = env["sedar.ais.position"].search([("tugboat_id", "=", tug.id)], limit=1)
            if position:
                position.write(values)
            else:
                values["tugboat_id"] = tug.id
                env["sedar.ais.position"].create(values)
        return True

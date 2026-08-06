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
    def _crew_payload(self, tugboat):
        assignment = self.env["sedar.tug.assignment"].search(
            [
                ("tugboat_id", "=", tugboat.id),
                ("state", "!=", "cancelled"),
                ("order_id.state", "in", ["ready", "dispatched", "in_progress"]),
            ],
            order="planned_start desc, id desc",
            limit=1,
        )
        crew = assignment.requirement_ids.mapped("crew_assignment_ids").filtered(
            lambda item: item.state != "rejected"
        ).mapped("crew_profile_id")
        crew_source = "Current operation"
        if not crew:
            crew = tugboat.home_crew_ids.filtered("active")
            crew_source = "Home crew roster"
        return assignment, crew_source, [
            {
                "id": profile.id,
                "name": profile.employee_id.name,
                "rank": profile.rank_id.name,
                "availability": profile.availability_status,
            }
            for profile in crew.sorted(lambda item: (item.rank_id.sequence, item.employee_id.name))
        ]

    @api.model
    def get_dashboard_data(self):
        if not self.env.user.has_group("sedar_ais_demo.group_sedar_ais_user") and not self.env.su:
            raise AccessError("You do not have access to simulated AIS fleet monitoring.")
        can_advance = self.env.su or self.env.user.has_group("sedar_ais_demo.group_sedar_ais_manager")
        dashboard = self.sudo()
        tugs = dashboard.env["sedar.tugboat"].search([("active", "=", True)], order="name")
        positions = {item.tugboat_id.id: item for item in dashboard.search([("tugboat_id", "in", tugs.ids)])}
        payload = []
        now = fields.Datetime.now()
        for tug in tugs:
            position = positions.get(tug.id)
            if not position:
                continue
            drydock = dashboard.env["sedar.drydock.plan"].search(
                [("tugboat_id", "=", tug.id), ("state", "in", ["planned", "in_progress"])],
                order="planned_start desc", limit=1,
            )
            blockers = dashboard.env["maintenance.request"].search_count([
                ("sedar_tugboat_id", "=", tug.id),
                ("sedar_blocks_tug_readiness", "=", True),
            ])
            assignment, crew_source, crew = dashboard._crew_payload(tug)
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

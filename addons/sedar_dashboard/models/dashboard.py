from datetime import timedelta

from odoo import api, fields, models


class SedarDashboard(models.Model):
    _name = 'sedar.dashboard'
    _description = 'Management KPI Dashboard'

    name = fields.Char(default='SEDAR KPI Snapshot')
    active_jobs = fields.Integer(compute='_compute_kpis')
    vessel_utilization = fields.Float(compute='_compute_kpis', string='Vessel Utilization %')
    open_incidents = fields.Integer(compute='_compute_kpis')
    expiring_documents = fields.Integer(compute='_compute_kpis')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    monthly_revenue = fields.Monetary(compute='_compute_kpis', currency_field='currency_id')

    @api.model
    def get_owner_snapshot(self):
        """Return one owner-friendly, drillable snapshot from live ERP records."""
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        warning_date = today + timedelta(days=30)
        Vessel = self.env['sedar.vessel']
        Job = self.env['sedar.job.order']
        Incident = self.env['sedar.hsse.incident']
        Invoice = self.env['account.move']

        vessels = Vessel.search([], order='name')
        open_jobs = Job.search_count([('state', 'not in', ['completed', 'billed'])])
        open_incidents = Incident.search_count([('state', '!=', 'closed')])
        critical_incidents = Incident.search_count([
            ('state', '!=', 'closed'), ('severity', 'in', ['high', 'critical']),
        ])
        open_investigations = Incident.search_count([
            ('state', '!=', 'closed'), ('severity', 'not in', ['high', 'critical']),
        ])
        requested_jobs = Job.search_count([('state', '=', 'requested')])
        delayed_jobs = Job.search_count([
            ('state', '=', 'requested'), ('delay_reason', 'not in', [False, '']),
        ]) if 'delay_reason' in Job._fields else 0
        invoices = Invoice.search([
            ('move_type', '=', 'out_invoice'), ('invoice_date', '>=', month_start),
            ('state', '=', 'posted'),
        ])
        overdue_domain = [
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'not in', ['paid', 'reversed']),
            ('invoice_date_due', '<', today),
        ]
        overdue_invoices = Invoice.search(overdue_domain)

        expiry_sources = [
            ('sedar.hsse.permit', 'Permits', 'sedar_hsse.action_sedar_hsse_permit'),
            ('sedar.crew.certification', 'Crew certificates', 'sedar_crewing.action_sedar_crew_certification'),
            ('sedar.crew.medical', 'Crew medicals', 'sedar_crewing.action_sedar_crew_medical'),
            ('sedar.doc.contract', 'Contracts', 'sedar_doccontrol.action_sedar_doc_contract'),
            ('sedar.doc.vessel.cert', 'Vessel certificates', 'sedar_doccontrol.action_sedar_doc_vessel_cert'),
            ('sedar.doc.insurance', 'Insurance policies', 'sedar_doccontrol.action_sedar_doc_insurance'),
            ('sedar.doc.record', 'Controlled documents', 'sedar_doccontrol.action_sedar_doc_record'),
        ]
        expiry_counts = []
        for model_name, label, action in expiry_sources:
            count = self.env[model_name].search_count([
                ('expiry_date', '!=', False), ('expiry_date', '<=', warning_date),
            ])
            if count:
                expiry_counts.append({'label': label, 'count': count, 'action': action})
        expiring_total = sum(item['count'] for item in expiry_counts)
        maintenance_statuses = ('maintenance', 'dry_dock', 'off_hire')
        blocked_vessels = vessels.filtered(lambda vessel: vessel.status in maintenance_statuses)
        stale_vessels = vessels.filtered(lambda vessel: vessel.tracking_status != 'online')
        overdue_maintenance = False
        if 'sedar.maintenance.work.order' in self.env:
            MaintenanceWork = self.env['sedar.maintenance.work.order']
            overdue_maintenance = MaintenanceWork.search([
                ('status', '!=', 'done'), ('due_date', '!=', False), ('due_date', '<', today),
            ])

        alerts = []
        if critical_incidents:
            alerts.append(self._owner_alert(
                'critical', 'Safety action required',
                f'{critical_incidents} high or critical safety event(s) remain open.',
                'sedar_hsse.action_sedar_hsse_incident', 'Safety & Compliance',
            ))
        if blocked_vessels:
            alerts.append(self._owner_alert(
                'critical', 'Vessels unavailable for dispatch',
                ', '.join(blocked_vessels.mapped('name')) + ' currently in dry dock.',
                'sedar_tug_ops.action_sedar_vessel', 'Fleet & Jobs',
            ))
        if overdue_maintenance:
            critical_maintenance = len(overdue_maintenance.filtered(
                lambda work: work.severity in ('high', 'critical')
            ))
            detail = f'{len(overdue_maintenance)} overdue work order(s) require technical follow-up.'
            if critical_maintenance:
                detail = f'{critical_maintenance} critical or high-priority work order(s) are overdue.'
            alerts.append(self._owner_alert(
                'warning', 'Maintenance work overdue', detail,
                'sedar_marine_mvp.action_sedar_maintenance_work_order', 'Maintenance',
            ))
        if overdue_invoices:
            alerts.append(self._owner_alert(
                'warning', 'Customer payments overdue',
                f'{len(overdue_invoices)} invoice(s) totaling {self._owner_money(sum(overdue_invoices.mapped("amount_residual")))} need collection follow-up.',
                'account.action_move_out_invoice_type', 'Finance',
            ))
        if open_investigations:
            alerts.append(self._owner_alert(
                'info', 'Safety investigations remain open',
                f'{open_investigations} safety event(s) still require investigation or closure.',
                'sedar_hsse.action_sedar_hsse_incident', 'Safety & Compliance',
            ))
        if requested_jobs:
            detail = f'{requested_jobs} requested job(s) still require dispatch confirmation.'
            if delayed_jobs:
                detail = f'{requested_jobs} requested job(s); {delayed_jobs} report a dispatch delay.'
            alerts.append(self._owner_alert(
                'info', 'Jobs awaiting dispatch', detail,
                'sedar_tug_ops.action_sedar_job_order', 'Fleet & Jobs',
            ))
        if expiring_total:
            summary = ', '.join(f'{item["count"]} {item["label"].lower()}' for item in expiry_counts[:3])
            alerts.append(self._owner_alert(
                'warning', 'Documents need renewal', summary + '.',
                expiry_counts[0]['action'], 'Safety & Compliance',
            ))
        if stale_vessels:
            alerts.append(self._owner_alert(
                'info', 'Vessel positions need confirmation',
                f'{len(stale_vessels)} vessel tracker(s) are stale or offline.',
                'sedar_tug_ops.action_sedar_vessel_tracking_log', 'Fleet & Jobs',
            ))
        if not alerts:
            alerts.append(self._owner_alert(
                'good', 'No critical exceptions',
                'No urgent safety, collection, dispatch, or compliance exception was detected.',
                'sedar_tug_ops.action_sedar_job_order', 'Owner Overview',
            ))

        alerts = alerts[:6]

        available = len(vessels.filtered(lambda vessel: vessel.status not in maintenance_statuses))
        availability = round((available / len(vessels) * 100), 1) if vessels else 0
        return {
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'metrics': [
                self._owner_metric('Fleet availability', f'{availability:g}%', f'{available} of {len(vessels)} vessels ready', 'fa-anchor', 'good', 'sedar_tug_ops.action_sedar_vessel'),
                self._owner_metric('Jobs in progress', str(open_jobs), 'Requested, dispatched, or underway', 'fa-briefcase', 'good', 'sedar_tug_ops.action_sedar_job_order'),
                self._owner_metric('Revenue this month', self._owner_money(sum(invoices.mapped('amount_total'))), f'{len(invoices)} posted invoice(s)', 'fa-bar-chart', 'good', 'account.action_move_out_invoice_type'),
                self._owner_metric('Items needing attention', str(len(alerts)), 'Safety, cash, fleet, and compliance', 'fa-bell', 'risk' if critical_incidents or blocked_vessels else 'watch', False),
            ],
            'summary': {
                'total_vessels': len(vessels), 'available_vessels': available,
                'open_jobs': open_jobs, 'open_incidents': open_incidents,
                'expiring_documents': expiring_total,
                'overdue_receivables': self._owner_money(sum(overdue_invoices.mapped('amount_residual'))),
            },
            'alerts': alerts,
            'vessels': [self._owner_vessel(vessel, index) for index, vessel in enumerate(vessels)],
        }

    @api.model
    def _owner_money(self, amount):
        return f'PHP {amount:,.0f}'

    @api.model
    def _owner_metric(self, label, value, note, icon, tone, action):
        return {'label': label, 'value': value, 'note': note, 'icon': icon, 'className': f'is-{tone}', 'action': action}

    @api.model
    def _owner_alert(self, severity, title, detail, action, area):
        return {'severity': severity, 'title': title, 'detail': detail, 'action': action, 'area': area}

    @api.model
    def _owner_vessel(self, vessel, index=0):
        on_maintenance = vessel.status in ('maintenance', 'dry_dock', 'off_hire')
        tone = 'watch' if on_maintenance else 'good'
        location = getattr(vessel, 'last_known_location', False) or vessel.home_port or 'Location not recorded'
        latitude = vessel.current_latitude
        longitude = vessel.current_longitude
        power = getattr(vessel, 'horsepower', 0) or getattr(vessel, 'capacity', 0)
        bollard_pull = getattr(vessel, 'bollard_pull', 0)
        fuel_on_hand = getattr(vessel, 'fuel_on_hand', 0)
        availability_rate = getattr(vessel, 'availability_rate', 0)
        utilization_rate = getattr(vessel, 'utilization_rate', 0)
        last_update = getattr(vessel, 'last_position_at', False) or getattr(vessel, 'ais_timestamp', False)
        map_positions = [
            (18, 14), (32, 43), (15, 78),
            (58, 18), (45, 57), (64, 84),
            (72, 10), (68, 48), (74, 76),
        ]
        lat, lng = map_positions[index % len(map_positions)]
        return {
            'id': vessel.id, 'name': vessel.name,
            'role': dict(vessel._fields['vessel_type'].selection).get(vessel.vessel_type, 'Vessel'),
            'status': 'On Maintenance' if on_maintenance else 'Active', 'statusClass': f'is-{tone}',
            'location': location,
            'speed': f'{vessel.speed_knots:g} kn',
            'heading': f'{vessel.course_degrees:g} deg',
            'tracking': dict(vessel._fields['tracking_status'].selection).get(vessel.tracking_status, 'Offline'),
            'power': f'{power:,.0f} HP' if power else False,
            'bollard': f'{bollard_pull:g} t' if bollard_pull else False,
            'fuelOnHand': f'{fuel_on_hand:,.0f}' if fuel_on_hand else False,
            'availabilityRate': f'{availability_rate:g}%' if availability_rate else False,
            'utilizationRate': f'{utilization_rate:g}%' if utilization_rate else False,
            'lastUpdate': fields.Datetime.to_string(last_update) if last_update else False,
            'latitude': latitude, 'longitude': longitude,
            # Positions on the prototype canvas are only a visual distribution.
            'lat': lat, 'lng': lng,
            'engine': 'Equipment register planned',
            'horsepower': f'{vessel.capacity:g} BHP' if vessel.capacity else 'Not recorded',
            'bollard': 'Not recorded', 'fuel': 0,
            'availability': 0 if on_maintenance else 100,
            'parts': [],
        }

    def _compute_kpis(self):
        job_order = self.env['sedar.job.order']
        vessel = self.env['sedar.vessel']
        incident = self.env['sedar.hsse.incident']
        invoice = self.env['account.move']
        expiry_models = [
            'sedar.hsse.permit',
            'sedar.crew.certification',
            'sedar.crew.medical',
            'sedar.doc.contract',
            'sedar.doc.vessel.cert',
            'sedar.doc.insurance',
            'sedar.doc.record',
        ]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for rec in self:
            total_vessels = vessel.search_count([])
            active_vessels = vessel.search_count([('status', '=', 'active')])
            rec.active_jobs = job_order.search_count([('state', 'not in', ['completed', 'billed'])])
            rec.vessel_utilization = (active_vessels / total_vessels * 100) if total_vessels else 0.0
            rec.open_incidents = incident.search_count([('state', '!=', 'closed')])
            rec.expiring_documents = sum(
                self.env[model].search_count([('expiry_status', 'in', ['warning', 'expired'])])
                for model in expiry_models
            )
            invoices = invoice.search([
                ('move_type', '=', 'out_invoice'),
                ('invoice_date', '>=', month_start),
                ('state', '=', 'posted'),
            ])
            rec.monthly_revenue = sum(invoices.mapped('amount_total'))

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarMarketingRecord(models.Model):
    _inherit = 'sedar.marketing.record'

    assigned_tug_id = fields.Many2one('sedar.vessel', string='Assigned SEDAR Tug')
    job_order_id = fields.Many2one('sedar.job.order', string='Operations Job', readonly=True, copy=False)

    def action_create_job_order(self):
        self.ensure_one()
        if self.job_order_id:
            return self._open_record(self.job_order_id)
        if not self.assigned_tug_id:
            raise UserError('Assign an available SEDAR tug before creating the operations job.')
        if not self.company_name:
            raise UserError('Enter the customer company name first.')

        partner = self.env['res.partner'].search([('name', '=ilike', self.company_name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.company_name,
                'phone': self.mobile_number or self.telephone_number,
                'street': self.company_address,
                'customer_rank': 1,
            })
        requested_at = fields.Datetime.now()
        if self.requested_date:
            requested_at = fields.Datetime.to_datetime(self.requested_date)
        job = self.env['sedar.job.order'].create({
            'customer_id': partner.id,
            'vessel_id': self.assigned_tug_id.id,
            'origin_port': self.pickup_location,
            'destination_port': self.destination,
            'requested_date': requested_at,
            'marketing_request_id': self.id,
        })
        self.write({'job_order_id': job.id, 'status': 'scheduled'})
        return self._open_record(job)

    def action_open_job_order(self):
        self.ensure_one()
        if not self.job_order_id:
            raise UserError('Create the operations job first.')
        return self._open_record(self.job_order_id)

    def _open_record(self, record):
        return {
            'type': 'ir.actions.act_window',
            'res_model': record._name,
            'res_id': record.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SedarJobOrder(models.Model):
    _inherit = 'sedar.job.order'

    marketing_request_id = fields.Many2one('sedar.marketing.record', string='Source Request', copy=False)
    crew_ids = fields.Many2many('sedar.crew.member', string='Assigned Crew')
    schedule_ids = fields.One2many('sedar.tug.schedule', 'job_order_id', string='Schedules')
    operational_voyage_ids = fields.One2many('sedar.voyage.log', 'job_order_id', string='Voyages')
    fuel_log_ids = fields.One2many('sedar.fuel.log', 'job_order_id', string='Fuel Logs')
    billing_ids = fields.One2many('sedar.towage.billing', 'job_order_id', string='Towage Bills')
    readiness_state = fields.Selection(
        [('not_ready', 'Not Ready'), ('warning', 'Needs Review'), ('ready', 'Ready')],
        compute='_compute_readiness',
        string='Dispatch Readiness',
    )
    readiness_note = fields.Char(compute='_compute_readiness')
    schedule_count = fields.Integer(compute='_compute_counts')
    voyage_count = fields.Integer(compute='_compute_counts')
    fuel_count = fields.Integer(compute='_compute_counts')
    billing_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_counts')
    quoted_amount = fields.Monetary(currency_field='currency_id')
    direct_cost = fields.Monetary(currency_field='currency_id')
    gross_profit = fields.Monetary(compute='_compute_profit', currency_field='currency_id', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('quoted_amount', 'direct_cost')
    def _compute_profit(self):
        for job in self:
            job.gross_profit = job.quoted_amount - job.direct_cost

    @api.depends(
        'crew_ids',
        'crew_ids.vessel_id',
        'crew_ids.employee_id',
        'vessel_id',
        'vessel_id.status',
    )
    def _compute_readiness(self):
        today = fields.Date.context_today(self)
        for job in self:
            reasons = []
            if not job.vessel_id or job.vessel_id.status not in ('active', 'available', 'standby'):
                reasons.append('vessel is not available')
            if not job.crew_ids:
                reasons.append('no crew assigned')
            elif any(not crew.employee_id for crew in job.crew_ids):
                reasons.append('crew employee record is incomplete')
            if job.crew_ids:
                expired_certs = self.env['sedar.crew.certification'].search_count([
                    ('crew_id', 'in', job.crew_ids.ids),
                    ('expiry_date', '<', today),
                ])
                invalid_medicals = self.env['sedar.crew.medical'].search_count([
                    ('crew_id', 'in', job.crew_ids.ids),
                    '|', ('fit_for_duty', '=', False), ('expiry_date', '<', today),
                ])
                if expired_certs:
                    reasons.append('crew certification is expired')
                if invalid_medicals:
                    reasons.append('crew medical clearance is invalid')
            job.readiness_state = 'not_ready' if reasons else 'ready'
            job.readiness_note = ', '.join(reasons).capitalize() if reasons else 'Vessel and crew checks passed.'

    @api.depends('schedule_ids', 'operational_voyage_ids', 'fuel_log_ids', 'billing_ids', 'billing_ids.invoice_id')
    def _compute_counts(self):
        for job in self:
            job.schedule_count = len(job.schedule_ids)
            job.voyage_count = len(job.operational_voyage_ids)
            job.fuel_count = len(job.fuel_log_ids)
            job.billing_count = len(job.billing_ids)
            job.invoice_count = len(job.billing_ids.mapped('invoice_id'))

    def action_dispatch(self):
        for job in self:
            if job.readiness_state != 'ready':
                raise UserError('This job is not ready to dispatch: %s' % job.readiness_note)
            if not job.schedule_ids:
                job._create_schedule()
        return super().action_dispatch()

    def action_start(self):
        result = super().action_start()
        for job in self:
            job.schedule_ids.filtered(lambda item: item.state in ('planned', 'confirmed')).write({'state': 'in_progress'})
            if not job.operational_voyage_ids:
                job._create_voyage()
        return result

    def action_complete(self):
        now = fields.Datetime.now()
        for job in self:
            if not job.operational_voyage_ids:
                raise UserError('Add a voyage log before completing this job.')
            job.operational_voyage_ids.filtered(lambda voyage: not voyage.arrival_time).write({'arrival_time': now})
            job.schedule_ids.filtered(lambda item: item.state != 'cancelled').write({'state': 'done'})
        return super().action_complete()

    def action_create_schedule(self):
        self.ensure_one()
        schedule = self._create_schedule()
        return self._open_records('sedar.tug.schedule', schedule.ids)

    def _create_schedule(self):
        self.ensure_one()
        start = self.requested_date or fields.Datetime.now()
        return self.env['sedar.tug.schedule'].create({
            'name': '%s - %s' % (self.name, self.vessel_id.name),
            'vessel_id': self.vessel_id.id,
            'job_order_id': self.id,
            'start_datetime': start,
            'end_datetime': start + timedelta(hours=4),
            'port_area': self.origin_port or self.vessel_id.home_port or 'Port Area',
            'assignment_type': 'towage',
        })

    def action_create_voyage(self):
        self.ensure_one()
        voyage = self._create_voyage()
        return self._open_records('sedar.voyage.log', voyage.ids)

    def _create_voyage(self):
        self.ensure_one()
        now = fields.Datetime.now()
        return self.env['sedar.voyage.log'].create({
            'job_order_id': self.id,
            'departure_time': now,
        })

    def action_add_fuel_log(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sedar.fuel.log',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_job_order_id': self.id, 'default_vessel_id': self.vessel_id.id},
        }

    def action_create_billing(self):
        self.ensure_one()
        if self.state != 'completed':
            raise UserError('Complete the job before creating billing.')
        bill = self.billing_ids[:1]
        if not bill:
            bill = self.env['sedar.towage.billing'].create({
                'name': 'Towage Service - %s' % self.name,
                'job_order_id': self.id,
                'rate_basis': 'job',
                'rate': self.quoted_amount or 1.0,
            })
        return self._open_records('sedar.towage.billing', bill.ids)

    def action_open_schedules(self):
        return self._open_records('sedar.tug.schedule', self.schedule_ids.ids)

    def action_open_voyages(self):
        return self._open_records('sedar.voyage.log', self.operational_voyage_ids.ids)

    def action_open_fuel_logs(self):
        return self._open_records('sedar.fuel.log', self.fuel_log_ids.ids)

    def action_open_billings(self):
        return self._open_records('sedar.towage.billing', self.billing_ids.ids)

    def action_open_invoices(self):
        return self._open_records('account.move', self.billing_ids.mapped('invoice_id').ids)

    def _open_records(self, model, ids):
        self.ensure_one()
        action = {'type': 'ir.actions.act_window', 'res_model': model, 'view_mode': 'tree,form', 'target': 'current'}
        if len(ids) == 1:
            action.update({'res_id': ids[0], 'view_mode': 'form'})
        else:
            action['domain'] = [('id', 'in', ids)]
        return action


class SedarFuelLog(models.Model):
    _inherit = 'sedar.fuel.log'

    job_order_id = fields.Many2one('sedar.job.order', string='Job Order', ondelete='set null')
    voyage_id = fields.Many2one('sedar.voyage.log', string='Voyage', ondelete='set null')

    @api.onchange('job_order_id')
    def _onchange_job_order_id(self):
        if self.job_order_id:
            self.vessel_id = self.job_order_id.vessel_id


class SedarTowageBilling(models.Model):
    _inherit = 'sedar.towage.billing'

    payment_state = fields.Selection(related='invoice_id.payment_state', string='Payment Status', readonly=True)

    def action_create_invoice(self):
        result = super().action_create_invoice()
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError('Create the invoice first.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SedarCrewRotation(models.Model):
    _inherit = 'sedar.crew.rotation'

    def action_confirm(self):
        self.write({'state': 'onboard'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class SedarCrewLeave(models.Model):
    _inherit = 'sedar.crew.leave'

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for leave in self:
            if leave.date_from and leave.date_to and leave.date_to < leave.date_from:
                raise ValidationError('Leave end date cannot be before the start date.')

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})


class SedarHsseCorrectiveAction(models.Model):
    _name = 'sedar.hsse.corrective.action'
    _description = 'HSSE Corrective Action'
    _order = 'due_date, id'

    name = fields.Char(required=True)
    incident_id = fields.Many2one('sedar.hsse.incident', required=True, ondelete='cascade')
    vessel_id = fields.Many2one(related='incident_id.vessel_id', store=True)
    owner_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    due_date = fields.Date(required=True)
    state = fields.Selection(
        [('open', 'Open'), ('in_progress', 'In Progress'), ('done', 'Done')],
        default='open',
        required=True,
    )
    overdue = fields.Boolean(compute='_compute_overdue')
    notes = fields.Text()

    @api.depends('due_date', 'state')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for action in self:
            action.overdue = bool(action.due_date) and action.state != 'done' and action.due_date < today

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})


class SedarHsseIncident(models.Model):
    _inherit = 'sedar.hsse.incident'

    job_order_id = fields.Many2one('sedar.job.order', string='Job Order')
    action_ids = fields.One2many('sedar.hsse.corrective.action', 'incident_id', string='Corrective Actions')
    risk_assessment_ids = fields.One2many('sedar.hsse.risk.assessment', 'incident_id', string='Risk Assessments')
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user)

    def _check_close_requirements(self):
        super()._check_close_requirements()
        for event in self:
            incomplete_actions = event.action_ids.filtered(lambda action: action.state != 'done')
            if incomplete_actions:
                raise UserError('Complete all corrective actions before closing this safety event.')
            if event.classification in ('major', 'reportable'):
                if not event.risk_assessment_ids:
                    raise UserError('Add a risk assessment before closing this safety event.')
                if not event.action_ids:
                    raise UserError('Add and complete a corrective action before closing this safety event.')


class SedarDocVesselCert(models.Model):
    _inherit = 'sedar.doc.vessel.cert'

    renewal_state = fields.Selection(
        [('valid', 'Valid'), ('renewal', 'Renewal In Progress'), ('review', 'For Review')],
        default='valid',
        required=True,
    )
    renewal_owner_id = fields.Many2one('res.users', string='Renewal Owner')
    attachment = fields.Binary()
    attachment_name = fields.Char()

    def action_start_renewal(self):
        self.write({'renewal_state': 'renewal', 'renewal_owner_id': self.env.user.id})

    def action_submit_review(self):
        self.write({'renewal_state': 'review'})

    def action_mark_renewed(self):
        for certificate in self:
            if not certificate.expiry_date:
                raise UserError('Set the new expiry date before marking the certificate renewed.')
        self.write({'renewal_state': 'valid'})

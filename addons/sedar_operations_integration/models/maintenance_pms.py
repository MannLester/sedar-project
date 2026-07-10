from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    current_meter_hours = fields.Float(readonly=True, copy=False)
    last_meter_date = fields.Date(readonly=True, copy=False)
    meter_reading_ids = fields.One2many('sedar.equipment.meter', 'equipment_id')
    maintenance_plan_ids = fields.One2many('sedar.maintenance.plan', 'equipment_id')
    service_log_ids = fields.One2many('sedar.maintenance.service.log', 'equipment_id')


class SedarMaintenancePlan(models.Model):
    _name = 'sedar.maintenance.plan'
    _description = 'Planned Maintenance Schedule'
    _order = 'next_due_date, next_due_meter_hours, id'

    name = fields.Char(required=True)
    equipment_id = fields.Many2one('maintenance.equipment', required=True, ondelete='cascade', index=True)
    vessel_id = fields.Many2one(related='equipment_id.vessel_id', store=True, readonly=True)
    company_id = fields.Many2one(related='equipment_id.company_id', store=True, readonly=True)
    trigger_type = fields.Selection(
        [('calendar', 'Calendar'), ('meter', 'Running Hours'), ('both', 'Calendar and Running Hours')],
        default='calendar',
        required=True,
    )
    interval_days = fields.Integer(default=30)
    interval_meter_hours = fields.Float()
    next_due_date = fields.Date()
    next_due_meter_hours = fields.Float()
    estimated_duration = fields.Float(default=1.0)
    severity = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='medium',
        required=True,
    )
    blocks_operation = fields.Boolean()
    assigned_user_id = fields.Many2one('res.users')
    checklist_template_ids = fields.One2many('sedar.maintenance.plan.check', 'plan_id', copy=True)
    part_template_ids = fields.One2many('sedar.maintenance.plan.part', 'plan_id', copy=True)
    work_order_ids = fields.One2many('maintenance.request', 'sedar_plan_id')
    last_generated_at = fields.Datetime(readonly=True, copy=False)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    @api.constrains('trigger_type', 'interval_days', 'interval_meter_hours', 'next_due_date', 'next_due_meter_hours')
    def _check_trigger_values(self):
        for plan in self:
            if plan.trigger_type in ('calendar', 'both'):
                if plan.interval_days <= 0 or not plan.next_due_date:
                    raise ValidationError('Calendar plans require a positive day interval and next due date.')
            if plan.trigger_type in ('meter', 'both'):
                if plan.interval_meter_hours <= 0 or plan.next_due_meter_hours <= 0:
                    raise ValidationError('Meter plans require a positive hour interval and next due meter value.')

    def _is_due(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        calendar_due = self.trigger_type in ('calendar', 'both') and self.next_due_date <= today
        meter_due = (
            self.trigger_type in ('meter', 'both')
            and self.equipment_id.current_meter_hours >= self.next_due_meter_hours
        )
        return calendar_due or meter_due

    def action_generate_work_order(self):
        self.ensure_one()
        existing = self.work_order_ids.filtered(lambda request: not request.done and not request.archive)[:1]
        if existing:
            return existing
        schedule_date = fields.Datetime.now()
        if self.next_due_date:
            schedule_date = fields.Datetime.to_datetime(self.next_due_date)
        request = self.env['maintenance.request'].create({
            'name': '%s - %s' % (self.name, self.equipment_id.name),
            'equipment_id': self.equipment_id.id,
            'maintenance_type': 'preventive',
            'schedule_date': schedule_date,
            'duration': self.estimated_duration,
            'user_id': self.assigned_user_id.id,
            'severity': self.severity,
            'blocks_operation': self.blocks_operation,
            'sedar_plan_id': self.id,
            'due_meter_hours': self.next_due_meter_hours,
            'checklist_ids': [
                (0, 0, {'name': item.name, 'sequence': item.sequence, 'required': item.required})
                for item in self.checklist_template_ids
            ],
            'part_line_ids': [
                (0, 0, {'product_id': item.product_id.id, 'required_qty': item.quantity})
                for item in self.part_template_ids
            ],
        })
        self.last_generated_at = fields.Datetime.now()
        return request

    @api.model
    def _cron_generate_due_work_orders(self):
        for plan in self.search([('active', '=', True)]):
            if plan._is_due():
                plan.action_generate_work_order()
        return True

    def _advance_after_completion(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        values = {}
        if self.trigger_type in ('calendar', 'both'):
            next_date = self.next_due_date or today
            while next_date <= today:
                next_date += timedelta(days=self.interval_days)
            values['next_due_date'] = next_date
        if self.trigger_type in ('meter', 'both'):
            values['next_due_meter_hours'] = max(
                self.next_due_meter_hours,
                self.equipment_id.current_meter_hours,
            ) + self.interval_meter_hours
        self.write(values)


class SedarMaintenancePlanCheck(models.Model):
    _name = 'sedar.maintenance.plan.check'
    _description = 'Planned Maintenance Checklist Template'
    _order = 'sequence, id'

    plan_id = fields.Many2one('sedar.maintenance.plan', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    required = fields.Boolean(default=True)


class SedarMaintenancePlanPart(models.Model):
    _name = 'sedar.maintenance.plan.part'
    _description = 'Planned Maintenance Part Template'

    plan_id = fields.Many2one('sedar.maintenance.plan', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float(default=1.0, required=True)

    @api.constrains('quantity')
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError('Planned part quantity must be greater than zero.')


class SedarEquipmentMeter(models.Model):
    _name = 'sedar.equipment.meter'
    _description = 'Equipment Running-Hour Reading'
    _order = 'reading_date desc, id desc'

    equipment_id = fields.Many2one('maintenance.equipment', required=True, ondelete='cascade', index=True)
    reading_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    meter_hours = fields.Float(required=True)
    source = fields.Selection([('manual', 'Manual'), ('engine', 'Engine'), ('import', 'Imported')], default='manual', required=True)
    recorded_by_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    notes = fields.Text()

    @api.model_create_multi
    def create(self, values_list):
        records = self.browse()
        for values in values_list:
            equipment = self.env['maintenance.equipment'].browse(values['equipment_id'])
            meter_hours = values.get('meter_hours', 0.0)
            if meter_hours < equipment.current_meter_hours:
                raise ValidationError('A running-hour reading cannot be lower than the current equipment meter.')
            record = super(SedarEquipmentMeter, self).create([values])
            equipment.write({
                'current_meter_hours': meter_hours,
                'last_meter_date': values.get('reading_date') or fields.Date.context_today(self),
            })
            records |= record
            due_plans = equipment.maintenance_plan_ids.filtered(lambda plan: plan.active and plan._is_due())
            for plan in due_plans:
                plan.action_generate_work_order()
        return records

    def write(self, values):
        if 'equipment_id' in values or 'meter_hours' in values or 'reading_date' in values:
            raise UserError('Meter readings are permanent. Create a correcting reading instead of editing one.')
        return super().write(values)

    def unlink(self):
        raise UserError('Meter readings are permanent and cannot be deleted.')


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    sedar_plan_id = fields.Many2one('sedar.maintenance.plan', copy=False, index=True)
    due_meter_hours = fields.Float(readonly=True)
    checklist_ids = fields.One2many('sedar.maintenance.check', 'maintenance_request_id')
    labor_ids = fields.One2many('sedar.maintenance.labor', 'maintenance_request_id')
    service_log_id = fields.Many2one('sedar.maintenance.service.log', readonly=True, copy=False)

    def action_complete_sedar(self):
        for request in self:
            incomplete = request.checklist_ids.filtered(lambda item: item.required and not item.done)
            if incomplete:
                raise UserError('Complete every required maintenance checklist item before closing the work order.')
            unfinished_issues = request.stock_issue_ids.filtered(lambda issue: issue.state not in ('done', 'cancelled'))
            if unfinished_issues:
                raise UserError('Complete or cancel all linked part consumption movements before closing the work order.')
        result = super().action_complete_sedar()
        for request in self:
            labor_cost = sum(request.labor_ids.mapped('cost'))
            part_cost = sum(
                line.quantity * line.product_id.standard_price
                for issue in request.stock_issue_ids.filtered(lambda item: item.state == 'done' and item.movement_type == 'consume')
                for line in issue.line_ids
            )
            request.actual_cost = labor_cost + part_cost
            if not request.service_log_id:
                log = self.env['sedar.maintenance.service.log'].sudo().create({
                    'maintenance_request_id': request.id,
                    'equipment_id': request.equipment_id.id,
                    'vessel_id': request.vessel_id.id,
                    'completion_date': request.close_date or fields.Date.context_today(self),
                    'meter_hours': request.equipment_id.current_meter_hours,
                    'downtime_hours': request.downtime_hours,
                    'labor_cost': labor_cost,
                    'part_cost': part_cost,
                    'total_cost': request.actual_cost,
                    'work_summary': request.description or request.name,
                })
                request.service_log_id = log
            if request.sedar_plan_id:
                request.sedar_plan_id._advance_after_completion()
        return result


class SedarMaintenanceCheck(models.Model):
    _name = 'sedar.maintenance.check'
    _description = 'Maintenance Work Checklist'
    _order = 'sequence, id'

    maintenance_request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    required = fields.Boolean(default=True)
    done = fields.Boolean()
    completed_by_id = fields.Many2one('res.users', readonly=True)
    completed_at = fields.Datetime(readonly=True)
    notes = fields.Text()

    def action_complete(self):
        self.write({'done': True, 'completed_by_id': self.env.user.id, 'completed_at': fields.Datetime.now()})

    def action_reset(self):
        self.write({'done': False, 'completed_by_id': False, 'completed_at': False})


class SedarMaintenanceLabor(models.Model):
    _name = 'sedar.maintenance.labor'
    _description = 'Maintenance Labor Entry'
    _order = 'work_date, id'

    maintenance_request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    work_date = fields.Date(default=fields.Date.context_today, required=True)
    hours = fields.Float(required=True)
    hourly_rate = fields.Monetary(required=True)
    cost = fields.Monetary(compute='_compute_cost', store=True)
    currency_id = fields.Many2one(related='maintenance_request_id.currency_id', store=True, readonly=True)
    notes = fields.Text()

    @api.depends('hours', 'hourly_rate')
    def _compute_cost(self):
        for labor in self:
            labor.cost = labor.hours * labor.hourly_rate

    @api.constrains('hours', 'hourly_rate')
    def _check_values(self):
        for labor in self:
            if labor.hours <= 0 or labor.hourly_rate < 0:
                raise ValidationError('Labor hours must be positive and the hourly rate cannot be negative.')


class SedarMaintenanceServiceLog(models.Model):
    _name = 'sedar.maintenance.service.log'
    _description = 'Locked Equipment Service History'
    _order = 'completion_date desc, id desc'

    maintenance_request_id = fields.Many2one('maintenance.request', required=True, ondelete='restrict', index=True)
    equipment_id = fields.Many2one('maintenance.equipment', required=True, ondelete='restrict', index=True)
    vessel_id = fields.Many2one('sedar.vessel', index=True)
    completion_date = fields.Date(required=True, index=True)
    meter_hours = fields.Float()
    downtime_hours = fields.Float()
    labor_cost = fields.Monetary()
    part_cost = fields.Monetary()
    total_cost = fields.Monetary()
    currency_id = fields.Many2one(related='maintenance_request_id.currency_id', store=True, readonly=True)
    work_summary = fields.Text(required=True)

    _sql_constraints = [
        ('maintenance_service_request_unique', 'unique(maintenance_request_id)', 'A work order can have only one service history entry.'),
    ]

    def write(self, values):
        raise UserError('Completed equipment service history is locked and cannot be edited.')

    def unlink(self):
        raise UserError('Completed equipment service history is locked and cannot be deleted.')

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    vessel_id = fields.Many2one('sedar.vessel', index=True)
    job_order_id = fields.Many2one('sedar.job.order', index=True)
    shift_type = fields.Selection(
        [('office', 'Office'), ('vessel', 'Vessel Duty'), ('standby', 'Standby')],
        default='office',
        required=True,
    )
    overtime_hours = fields.Float(compute='_compute_sedar_overtime', store=True)
    overtime_approved_by_id = fields.Many2one('res.users', readonly=True)

    @api.depends('worked_hours')
    def _compute_sedar_overtime(self):
        for attendance in self:
            attendance.overtime_hours = max(attendance.worked_hours - 8.0, 0.0)

    @api.constrains('shift_type', 'vessel_id')
    def _check_vessel_shift(self):
        if any(item.shift_type == 'vessel' and not item.vessel_id for item in self):
            raise ValidationError('Vessel duty attendance requires a vessel.')

    def action_approve_overtime(self):
        if not self.env.user.has_group('hr.group_hr_user'):
            raise UserError('Only an HR Officer can approve overtime.')
        self.write({'overtime_approved_by_id': self.env.user.id})


class SedarPerformanceCycle(models.Model):
    _name = 'sedar.performance.cycle'
    _description = 'Employee Performance Review Cycle'
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    review_ids = fields.One2many('sedar.performance.review', 'cycle_id')
    state = fields.Selection(
        [('draft', 'Draft'), ('active', 'Active'), ('closed', 'Closed')],
        default='draft',
        required=True,
    )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        if any(cycle.date_end < cycle.date_start for cycle in self):
            raise ValidationError('Performance cycle end cannot be before its start.')

    def action_activate(self):
        self.filtered(lambda cycle: cycle.state == 'draft').write({'state': 'active'})

    def action_close(self):
        for cycle in self:
            if cycle.review_ids.filtered(lambda review: review.state not in ('approved', 'cancelled')):
                raise UserError('Approve or cancel every performance review before closing the cycle.')
        self.write({'state': 'closed'})


class SedarPerformanceReview(models.Model):
    _name = 'sedar.performance.review'
    _description = 'Employee Performance Review'
    _order = 'cycle_id desc, employee_id'

    cycle_id = fields.Many2one('sedar.performance.cycle', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True)
    manager_id = fields.Many2one('hr.employee', required=True)
    goal_ids = fields.One2many('sedar.performance.goal', 'review_id', copy=True)
    overall_score = fields.Float(compute='_compute_score', store=True)
    employee_comments = fields.Text()
    manager_comments = fields.Text()
    approved_by_id = fields.Many2one('res.users', readonly=True)
    approval_date = fields.Datetime(readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('self_review', 'Self Review'), ('manager_review', 'Manager Review'),
         ('approved', 'Approved'), ('cancelled', 'Cancelled')],
        default='draft',
        required=True,
    )

    _sql_constraints = [
        ('cycle_employee_unique', 'unique(cycle_id, employee_id)', 'An employee can have only one review per cycle.'),
    ]

    @api.depends('goal_ids.score', 'goal_ids.weight')
    def _compute_score(self):
        for review in self:
            total_weight = sum(review.goal_ids.mapped('weight'))
            review.overall_score = (
                sum(goal.score * goal.weight for goal in review.goal_ids) / total_weight
                if total_weight else 0.0
            )

    def action_submit_self_review(self):
        for review in self:
            if review.state != 'draft' or not review.employee_comments:
                raise UserError('Add employee comments before submitting the self review.')
        self.write({'state': 'self_review'})

    def action_submit_manager_review(self):
        for review in self:
            if review.state != 'self_review' or not review.manager_comments or not review.goal_ids:
                raise UserError('Complete manager comments and scored goals before submitting the manager review.')
        self.write({'state': 'manager_review'})

    def action_approve(self):
        if not self.env.user.has_group('hr.group_hr_manager'):
            raise UserError('Only an HR Manager can approve performance reviews.')
        for review in self:
            if review.state != 'manager_review':
                raise UserError('Only completed manager reviews can be approved.')
        self.write({'state': 'approved', 'approved_by_id': self.env.user.id, 'approval_date': fields.Datetime.now()})


class SedarPerformanceGoal(models.Model):
    _name = 'sedar.performance.goal'
    _description = 'Performance Review Goal'

    review_id = fields.Many2one('sedar.performance.review', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True)
    target = fields.Text(required=True)
    result = fields.Text()
    weight = fields.Float(default=1.0, required=True)
    score = fields.Float(help='Score from 0 to 5.')

    @api.constrains('weight', 'score')
    def _check_values(self):
        for goal in self:
            if goal.weight <= 0 or not 0 <= goal.score <= 5:
                raise ValidationError('Goal weight must be positive and score must be from 0 to 5.')


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sedar_onboarded_employee_id = fields.Many2one('hr.employee', readonly=True, copy=False)

    def action_sedar_create_employee(self):
        self.ensure_one()
        if self.sedar_hiring_state != 'hired':
            raise UserError('Mark the applicant hired before creating an employee.')
        if self.sedar_onboarded_employee_id:
            return self.sedar_onboarded_employee_id
        employee = self.env['hr.employee'].create({
            'name': self.partner_name or self.name,
            'job_id': self.job_id.id,
            'work_email': self.email_from,
            'mobile_phone': self.partner_mobile or self.partner_phone,
        })
        self.write({'sedar_onboarded_employee_id': employee.id, 'emp_id': employee.id})
        return employee


class SedarCrewRotation(models.Model):
    _inherit = 'sedar.crew.rotation'

    @api.constrains('crew_id', 'onboard_date', 'offboard_date', 'state')
    def _check_rotation_conflicts(self):
        for rotation in self:
            if rotation.offboard_date and rotation.offboard_date < rotation.onboard_date:
                raise ValidationError('Rotation off-board date cannot be before on-board date.')
            if rotation.state == 'cancelled':
                continue
            domain = [
                ('id', '!=', rotation.id), ('crew_id', '=', rotation.crew_id.id),
                ('state', '!=', 'cancelled'),
                '|', ('offboard_date', '=', False), ('offboard_date', '>=', rotation.onboard_date),
            ]
            if rotation.offboard_date:
                domain.append(('onboard_date', '<=', rotation.offboard_date))
            if self.search_count(domain):
                raise ValidationError('This crew member already has an overlapping vessel rotation.')

    def action_confirm(self):
        today = fields.Date.context_today(self)
        for rotation in self:
            invalid_cert = self.env['sedar.crew.certification'].search_count([
                ('crew_id', '=', rotation.crew_id.id),
                '|', ('expiry_date', '<', today), ('verification_state', '!=', 'verified'),
            ])
            invalid_medical = self.env['sedar.crew.medical'].search_count([
                ('crew_id', '=', rotation.crew_id.id),
                '|', ('expiry_date', '<', today), ('verification_state', '!=', 'verified'),
            ])
            if invalid_cert or invalid_medical:
                raise UserError('Verify valid crew certifications and medicals before confirming rotation.')
        return super().action_confirm()


class SedarCrewLeave(models.Model):
    _inherit = 'sedar.crew.leave'

    def action_approve(self):
        for leave in self:
            overlap = self.search_count([
                ('id', '!=', leave.id), ('crew_id', '=', leave.crew_id.id), ('state', '=', 'approved'),
                ('date_from', '<=', leave.date_to), ('date_to', '>=', leave.date_from),
            ])
            rotations = self.env['sedar.crew.rotation'].search_count([
                ('crew_id', '=', leave.crew_id.id), ('state', 'in', ('planned', 'onboard')),
                ('onboard_date', '<=', leave.date_to),
                '|', ('offboard_date', '=', False), ('offboard_date', '>=', leave.date_from),
            ])
            if overlap or rotations:
                raise UserError('Crew leave overlaps approved leave or an active vessel rotation.')
        return super().action_approve()


class SedarStcwType(models.Model):
    _name = 'sedar.stcw.type'
    _description = 'Controlled STCW Certificate Type'
    _order = 'code'

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    validity_months = fields.Integer(default=60, required=True)
    required_for_dispatch = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [('stcw_code_unique', 'unique(code)', 'STCW code must be unique.')]


class SedarCrewCertification(models.Model):
    _inherit = 'sedar.crew.certification'

    stcw_type_id = fields.Many2one('sedar.stcw.type')
    issuer = fields.Char()
    attachment = fields.Binary()
    attachment_name = fields.Char()
    verification_state = fields.Selection(
        [('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')],
        default='pending', required=True,
    )
    verified_by_id = fields.Many2one('res.users', readonly=True)
    verified_at = fields.Datetime(readonly=True)

    def action_verify(self):
        for certificate in self:
            if not all((certificate.certificate_no, certificate.issuer, certificate.issue_date,
                        certificate.expiry_date, certificate.attachment)):
                raise UserError('Certificate number, issuer, dates, and attachment are required for verification.')
        self.write({'verification_state': 'verified', 'verified_by_id': self.env.user.id, 'verified_at': fields.Datetime.now()})


class SedarCrewMedical(models.Model):
    _inherit = 'sedar.crew.medical'

    attachment = fields.Binary()
    attachment_name = fields.Char()
    verification_state = fields.Selection(
        [('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')],
        default='pending', required=True,
    )
    verified_by_id = fields.Many2one('res.users', readonly=True)

    def action_verify(self):
        for medical in self:
            if not all((medical.exam_date, medical.expiry_date, medical.clinic, medical.attachment)) or not medical.fit_for_duty:
                raise UserError('A fit-for-duty medical with clinic, dates, and attachment is required.')
        self.write({'verification_state': 'verified', 'verified_by_id': self.env.user.id})

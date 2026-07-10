from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarHsseCorrectiveAction(models.Model):
    _inherit = 'sedar.hsse.corrective.action'

    incident_id = fields.Many2one('sedar.hsse.incident', required=False, ondelete='cascade')
    near_miss_id = fields.Many2one('sedar.hsse.near.miss', ondelete='cascade')
    inspection_id = fields.Many2one('sedar.hsse.inspection', ondelete='cascade')
    risk_assessment_id = fields.Many2one('sedar.hsse.risk.assessment', ondelete='cascade')
    vessel_id = fields.Many2one('sedar.vessel', compute='_compute_source', store=True)
    source_name = fields.Char(compute='_compute_source', store=True)
    completion_note = fields.Text()

    @api.depends(
        'incident_id', 'incident_id.vessel_id',
        'near_miss_id', 'near_miss_id.vessel_id',
        'inspection_id', 'inspection_id.vessel_id',
        'risk_assessment_id', 'risk_assessment_id.vessel_id',
    )
    def _compute_source(self):
        for action in self:
            source = action.incident_id or action.near_miss_id or action.inspection_id or action.risk_assessment_id
            action.source_name = source.display_name if source else False
            action.vessel_id = source.vessel_id if source and 'vessel_id' in source._fields else False

    @api.constrains('incident_id', 'near_miss_id', 'inspection_id', 'risk_assessment_id')
    def _check_source(self):
        for action in self:
            source_count = sum(bool(source) for source in (
                action.incident_id,
                action.near_miss_id,
                action.inspection_id,
                action.risk_assessment_id,
            ))
            if source_count != 1:
                raise ValidationError('A corrective action must belong to exactly one HSE record.')

    def action_done(self):
        for action in self:
            if not action.completion_note:
                raise UserError('Add a completion note before closing this corrective action.')
        return super().action_done()


class SedarHsseNearMiss(models.Model):
    _inherit = 'sedar.hsse.near.miss'

    state = fields.Selection(
        [('reported', 'Reported'), ('review', 'Under Review'), ('action', 'Action Required'), ('closed', 'Closed')],
        default='reported',
        required=True,
    )
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    job_order_id = fields.Many2one('sedar.job.order', string='Job Order')
    action_ids = fields.One2many('sedar.hsse.corrective.action', 'near_miss_id', string='Corrective Actions')

    def action_review(self):
        self.write({'state': 'review'})

    def action_require_action(self):
        for report in self:
            if not report.action_ids:
                raise UserError('Add at least one corrective action first.')
        self.write({'state': 'action'})

    def action_close(self):
        for report in self:
            if report.action_ids.filtered(lambda action: action.state != 'done'):
                raise UserError('Complete all corrective actions before closing this near miss.')
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'review'})


class SedarHsseInspection(models.Model):
    _inherit = 'sedar.hsse.inspection'

    state = fields.Selection(
        [('draft', 'Draft'), ('in_progress', 'In Progress'), ('action', 'Action Required'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        default='draft',
        required=True,
    )
    job_order_id = fields.Many2one('sedar.job.order', string='Job Order')
    failed_count = fields.Integer(compute='_compute_failed_count')
    action_ids = fields.One2many('sedar.hsse.corrective.action', 'inspection_id', string='Corrective Actions')

    @api.depends('line_ids.result')
    def _compute_failed_count(self):
        for inspection in self:
            inspection.failed_count = len(inspection.line_ids.filtered(lambda line: line.result == 'fail'))

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_finish(self):
        for inspection in self:
            if not inspection.line_ids:
                raise UserError('Add checklist items before finishing the inspection.')
            failed_lines = inspection.line_ids.filtered(lambda line: line.result == 'fail')
            for line in failed_lines:
                action_name = '%s: %s' % (inspection.name, line.item)
                if not inspection.action_ids.filtered(lambda action: action.name == action_name):
                    self.env['sedar.hsse.corrective.action'].create({
                        'name': action_name,
                        'inspection_id': inspection.id,
                        'due_date': fields.Date.add(fields.Date.context_today(self), days=7),
                        'notes': line.remarks,
                    })
            inspection.state = 'action' if failed_lines else 'completed'

    def action_close(self):
        for inspection in self:
            if inspection.action_ids.filtered(lambda action: action.state != 'done'):
                raise UserError('Complete all corrective actions before closing the inspection.')
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class SedarHsseRiskAssessment(models.Model):
    _inherit = 'sedar.hsse.risk.assessment'

    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    job_order_id = fields.Many2one('sedar.job.order', string='Job Order')
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('review', 'For Review'), ('approved', 'Approved'), ('mitigated', 'Mitigated')],
        default='draft',
        required=True,
    )
    risk_level = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        compute='_compute_risk_level',
        store=True,
    )
    residual_likelihood = fields.Selection(
        [('1', '1 - Rare'), ('2', '2 - Unlikely'), ('3', '3 - Possible'), ('4', '4 - Likely'), ('5', '5 - Almost Certain')],
        default='1',
        required=True,
    )
    residual_severity = fields.Selection(
        [('1', '1 - Minor'), ('2', '2 - Moderate'), ('3', '3 - Serious'), ('4', '4 - Major'), ('5', '5 - Catastrophic')],
        default='1',
        required=True,
    )
    residual_score = fields.Integer(compute='_compute_risk_level', store=True)
    action_ids = fields.One2many('sedar.hsse.corrective.action', 'risk_assessment_id', string='Controls')

    @api.depends('risk_score', 'residual_likelihood', 'residual_severity')
    def _compute_risk_level(self):
        for risk in self:
            score = risk.risk_score
            risk.risk_level = 'critical' if score >= 20 else 'high' if score >= 12 else 'medium' if score >= 5 else 'low'
            risk.residual_score = int(risk.residual_likelihood or 0) * int(risk.residual_severity or 0)

    def action_submit(self):
        for risk in self:
            if not risk.mitigation:
                raise UserError('Enter the planned controls before submitting this assessment.')
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_mark_mitigated(self):
        for risk in self:
            if risk.action_ids.filtered(lambda action: action.state != 'done'):
                raise UserError('Complete all control actions before marking this risk mitigated.')
            if risk.residual_score >= risk.risk_score:
                raise UserError('Residual risk must be lower than the original risk.')
        self.write({'state': 'mitigated'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class SedarHssePermit(models.Model):
    _inherit = 'sedar.hsse.permit'

    state = fields.Selection(
        [('valid', 'Valid'), ('renewal', 'Renewal In Progress'), ('review', 'For Review'), ('expired', 'Expired')],
        compute='_compute_state',
        inverse='_inverse_state',
        store=True,
    )
    workflow_state = fields.Selection(
        [('valid', 'Valid'), ('renewal', 'Renewal In Progress'), ('review', 'For Review')],
        default='valid',
        required=True,
    )
    renewal_owner_id = fields.Many2one('res.users', string='Renewal Owner')
    attachment = fields.Binary()
    attachment_name = fields.Char()

    @api.depends('workflow_state', 'expiry_date')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for permit in self:
            permit.state = 'expired' if permit.expiry_date and permit.expiry_date < today else permit.workflow_state

    def _inverse_state(self):
        for permit in self:
            if permit.state != 'expired':
                permit.workflow_state = permit.state

    def action_start_renewal(self):
        self.write({'workflow_state': 'renewal', 'renewal_owner_id': self.env.user.id})

    def action_submit_review(self):
        self.write({'workflow_state': 'review'})

    def action_approve_renewal(self):
        today = fields.Date.context_today(self)
        for permit in self:
            if not permit.expiry_date or permit.expiry_date <= today:
                raise UserError('Set a future expiry date before approving the renewal.')
            if not permit.attachment:
                raise UserError('Attach the renewed permit before approval.')
        self.write({'workflow_state': 'valid'})


class SedarHsseTraining(models.Model):
    _name = 'sedar.hsse.training'
    _description = 'HSSE Training Record'
    _inherit = ['sedar.expiry.mixin']
    _order = 'training_date desc, id desc'

    name = fields.Char(required=True)
    training_type = fields.Selection(
        [('safety', 'Safety'), ('security', 'Security'), ('environment', 'Environment'), ('emergency', 'Emergency Drill'), ('other', 'Other')],
        default='safety',
        required=True,
    )
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    trainer = fields.Char(required=True)
    training_date = fields.Date(required=True, default=fields.Date.context_today)
    attendee_ids = fields.Many2many('hr.employee', string='Attendees')
    state = fields.Selection(
        [('planned', 'Planned'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        default='planned',
        required=True,
    )
    notes = fields.Text()
    attachment = fields.Binary(string='Attendance / Certificate')
    attachment_name = fields.Char()

    def action_complete(self):
        for training in self:
            if not training.attendee_ids:
                raise UserError('Add at least one attendee before completing the training.')
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_planned(self):
        self.write({'state': 'planned'})

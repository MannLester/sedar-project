from odoo import fields, models
from odoo.exceptions import UserError


class SedarHsseIncident(models.Model):
    _name = 'sedar.hsse.incident'
    _description = 'HSSE Safety Event'
    _order = 'date desc'

    name = fields.Char(default='Safety Event', required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    reported_by_id = fields.Many2one('res.users', string='Reported By', default=lambda self: self.env.user, required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')
    location = fields.Char()
    classification = fields.Selection(
        [
            ('observation', 'Observation'),
            ('near_miss', 'Near Miss'),
            ('minor', 'Minor'),
            ('major', 'Major'),
            ('reportable', 'Reportable'),
        ],
    )
    severity = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='low',
        required=True,
    )
    description = fields.Text(required=True)
    report_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sedar_hsse_event_report_attachment_rel',
        'event_id',
        'attachment_id',
        string='Report Files and Photos',
    )
    corrective_action = fields.Text()
    review_note = fields.Text(string='Review Note')
    reviewed_by_id = fields.Many2one('res.users', string='Reviewed By', readonly=True, copy=False)
    reviewed_date = fields.Datetime(string='Reviewed On', readonly=True, copy=False)
    investigation_summary = fields.Text()
    investigation_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sedar_hsse_event_investigation_attachment_rel',
        'event_id',
        'attachment_id',
        string='Investigation Evidence',
    )
    regulatory_report_reference = fields.Char(string='Regulatory Filing Reference')
    state = fields.Selection(
        [
            ('open', 'Submitted'),
            ('review', 'Under Review'),
            ('investigating', 'Investigating'),
            ('closed', 'Closed'),
        ],
        default='open',
        string='Status',
        required=True,
    )

    def action_start_review(self):
        self.write({
            'state': 'review',
            'reviewed_by_id': self.env.user.id,
            'reviewed_date': fields.Datetime.now(),
        })

    def action_investigate(self):
        for event in self:
            if event.classification not in ('major', 'reportable'):
                raise UserError('Only Major or Reportable events require an investigation.')
        self.write({'state': 'investigating'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'review'})

    def write(self, vals):
        if vals.get('state') == 'closed':
            self._check_close_requirements()
        return super().write(vals)

    def _check_close_requirements(self):
        for event in self:
            if not event.classification:
                raise UserError('Classify this safety event before closing it.')
            if event.classification in ('observation', 'near_miss', 'minor') and not event.review_note:
                raise UserError('Add a review note before closing this safety event.')
            if event.classification in ('major', 'reportable') and not event.investigation_summary:
                raise UserError('Add the investigation summary before closing this safety event.')
            if event.classification in ('major', 'reportable') and not event.investigation_attachment_ids:
                raise UserError('Attach investigation evidence before closing this safety event.')
            if event.classification == 'reportable' and not event.regulatory_report_reference:
                raise UserError('Add the regulatory filing reference before closing this reportable event.')

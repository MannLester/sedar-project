from odoo import api, fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sedar_dispatch_id = fields.Many2one('sedar.job.dispatch', string='Job Dispatch Order')
    sedar_target_role = fields.Char(string='Target Role')
    sedar_vessel_id = fields.Many2one('sedar.vessel', string='Requested Boat')
    sedar_requirements_summary = fields.Text(string='Requirements / Documents')
    sedar_interview_datetime = fields.Datetime(string='Interview Schedule')
    sedar_interview_end = fields.Datetime(
        string='Interview End',
        compute='_compute_sedar_interview_end',
        store=True,
    )
    sedar_interview_mode = fields.Selection(
        [('online', 'Online'), ('face_to_face', 'Face to Face')],
        string='Interview Mode',
    )
    sedar_interview_location = fields.Char(string='Interview Link / Venue')
    sedar_calendar_color = fields.Integer(
        string='Calendar Color',
        compute='_compute_sedar_calendar_color',
        store=True,
    )
    sedar_attachment_ids = fields.One2many(
        'ir.attachment',
        'res_id',
        string='Submitted Documents',
        domain=[('res_model', '=', 'hr.applicant')],
    )
    sedar_attachment_count = fields.Integer(
        string='Document Count',
        compute='_compute_sedar_attachment_count',
    )
    sedar_hiring_state = fields.Selection(
        [
            ('application', 'Job Application'),
            ('for_interview', 'For Interview'),
            ('final_assessment', 'Final Assessment'),
            ('contract_signing', 'Contract Signing'),
            ('hired', 'Hired'),
        ],
        default='application',
        required=True,
        string='SEDAR Hiring Status',
        tracking=True,
    )

    @api.depends('sedar_interview_datetime')
    def _compute_sedar_interview_end(self):
        for applicant in self:
            if applicant.sedar_interview_datetime:
                applicant.sedar_interview_end = fields.Datetime.add(applicant.sedar_interview_datetime, hours=1)
            else:
                applicant.sedar_interview_end = False

    @api.depends('sedar_interview_mode', 'sedar_hiring_state')
    def _compute_sedar_calendar_color(self):
        for applicant in self:
            if applicant.sedar_hiring_state == 'for_interview':
                applicant.sedar_calendar_color = 4 if applicant.sedar_interview_mode == 'online' else 10
            elif applicant.sedar_hiring_state == 'final_assessment':
                applicant.sedar_calendar_color = 2
            else:
                applicant.sedar_calendar_color = 0

    def _compute_sedar_attachment_count(self):
        grouped = self.env['ir.attachment'].read_group(
            [('res_model', '=', 'hr.applicant'), ('res_id', 'in', self.ids)],
            ['res_id'],
            ['res_id'],
        )
        counts = {item['res_id']: item['res_id_count'] for item in grouped}
        for applicant in self:
            applicant.sedar_attachment_count = counts.get(applicant.id, 0)

    def action_sedar_for_interview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule Interview',
            'res_model': 'sedar.interview.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
                'default_interview_datetime': self.sedar_interview_datetime,
                'default_interview_mode': self.sedar_interview_mode or 'face_to_face',
                'default_interview_location': self.sedar_interview_location,
            },
        }

    def action_sedar_final_assessment(self):
        self.write({'sedar_hiring_state': 'final_assessment'})

    def action_sedar_contract_signing(self):
        self.write({'sedar_hiring_state': 'contract_signing'})

    def action_sedar_hired(self):
        self.write({'sedar_hiring_state': 'hired'})

    def action_sedar_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Submitted Documents',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [('res_model', '=', 'hr.applicant'), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': 'hr.applicant',
                'default_res_id': self.id,
            },
        }

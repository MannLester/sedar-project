from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sedar_dispatch_id = fields.Many2one('sedar.job.dispatch', string='Job Dispatch Order')
    sedar_target_role = fields.Char(string='Target Role')
    sedar_vessel_id = fields.Many2one('sedar.vessel', string='Requested Boat')
    sedar_requirements_summary = fields.Text(string='Requirements / Documents')
    sedar_interview_datetime = fields.Datetime(string='Interview Schedule')
    sedar_interview_duration = fields.Float(
        string='Interview Duration',
        default=1.0,
        help='Duration in hours.',
    )
    sedar_interview_end = fields.Datetime(
        string='Interview End',
        compute='_compute_sedar_interview_end',
        inverse='_inverse_sedar_interview_end',
        store=True,
    )
    sedar_interview_schedule_label = fields.Char(
        string='Interview Time',
        compute='_compute_sedar_interview_schedule_label',
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

    @api.depends('sedar_interview_datetime', 'sedar_interview_duration')
    def _compute_sedar_interview_end(self):
        for applicant in self:
            if applicant.sedar_interview_datetime:
                applicant.sedar_interview_end = fields.Datetime.add(
                    applicant.sedar_interview_datetime,
                    minutes=int(round((applicant.sedar_interview_duration or 1.0) * 60)),
                )
            else:
                applicant.sedar_interview_end = False

    def _inverse_sedar_interview_end(self):
        for applicant in self:
            if not applicant.sedar_interview_datetime or not applicant.sedar_interview_end:
                continue

            duration_seconds = (applicant.sedar_interview_end - applicant.sedar_interview_datetime).total_seconds()
            if duration_seconds <= 0:
                raise ValidationError(_('Interview end must be after the interview start.'))
            applicant.sedar_interview_duration = duration_seconds / 3600.0

    @api.depends('sedar_interview_datetime', 'sedar_interview_end')
    def _compute_sedar_interview_schedule_label(self):
        for applicant in self:
            if not applicant.sedar_interview_datetime:
                applicant.sedar_interview_schedule_label = False
                continue

            local_start = fields.Datetime.context_timestamp(applicant, applicant.sedar_interview_datetime)
            local_end = fields.Datetime.context_timestamp(applicant, applicant.sedar_interview_end)
            applicant.sedar_interview_schedule_label = '%s - %s' % (
                local_start.strftime('%b %d, %Y %I:%M %p'),
                local_end.strftime('%I:%M %p'),
            )

    @api.constrains(
        'sedar_hiring_state',
        'sedar_interview_datetime',
        'sedar_interview_end',
        'sedar_interview_duration',
        'sedar_interview_mode',
        'sedar_interview_location',
    )
    def _check_sedar_interview_schedule(self):
        for applicant in self:
            if applicant.sedar_hiring_state != 'for_interview':
                continue

            if not applicant.sedar_interview_datetime:
                raise ValidationError(_('Set an interview schedule before moving an applicant to Pending Interviews.'))
            if not applicant.sedar_interview_duration or applicant.sedar_interview_duration <= 0:
                raise ValidationError(_('Set a positive interview duration.'))
            if not applicant.sedar_interview_mode:
                raise ValidationError(_('Select an interview mode before scheduling the interview.'))
            if not applicant.sedar_interview_location:
                raise ValidationError(_('Set the interview link or venue before scheduling the interview.'))

            conflict = applicant._sedar_find_interview_conflict(
                applicant.sedar_interview_datetime,
                applicant.sedar_interview_duration,
            )
            if conflict:
                raise ValidationError(
                    _('This interview overlaps with %(candidate)s, scheduled from %(start)s to %(end)s.')
                    % {
                        'candidate': conflict.display_name,
                        'start': fields.Datetime.to_string(conflict.sedar_interview_datetime),
                        'end': fields.Datetime.to_string(conflict.sedar_interview_end),
                    }
                )

    def _sedar_find_interview_conflict(self, interview_datetime, interview_duration):
        self.ensure_one()
        if not interview_datetime:
            return self.env['hr.applicant']

        interview_end = fields.Datetime.add(interview_datetime, minutes=int(round((interview_duration or 1.0) * 60)))
        domain = [
            ('id', '!=', self.id),
            ('sedar_hiring_state', '=', 'for_interview'),
            ('sedar_interview_datetime', '<', interview_end),
            ('sedar_interview_end', '>', interview_datetime),
        ]
        return self.env['hr.applicant'].search(domain, limit=1, order='sedar_interview_datetime asc')

    def _sedar_next_interview_slot(self, interview_duration=1.0):
        self.ensure_one()
        duration_minutes = int(round((interview_duration or 1.0) * 60))
        step_minutes = 30
        start_hour = 8
        end_hour = 17
        local_now = fields.Datetime.context_timestamp(self, fields.Datetime.now())

        for day_offset in range(14):
            local_day = local_now + timedelta(days=day_offset)
            cursor = local_day.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_end = local_day.replace(hour=end_hour, minute=0, second=0, microsecond=0)

            if day_offset == 0 and local_now > cursor:
                base = local_now.replace(second=0, microsecond=0)
                minutes_to_add = step_minutes - (base.minute % step_minutes)
                cursor = base + timedelta(minutes=minutes_to_add or step_minutes)

            while cursor + timedelta(minutes=duration_minutes) <= day_end:
                utc_cursor = cursor.astimezone(pytz.utc).replace(tzinfo=None)
                if not self._sedar_find_interview_conflict(utc_cursor, interview_duration):
                    return utc_cursor
                cursor += timedelta(minutes=step_minutes)

        fallback = (local_now + timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
        return fallback.astimezone(pytz.utc).replace(tzinfo=None)

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
        default_interview_datetime = self.sedar_interview_datetime or self._sedar_next_interview_slot(
            self.sedar_interview_duration or 1.0
        )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule Interview',
            'res_model': 'sedar.interview.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
                'default_interview_datetime': fields.Datetime.to_string(default_interview_datetime),
                'default_interview_duration': self.sedar_interview_duration or 1.0,
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

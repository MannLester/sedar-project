from markupsafe import Markup, escape

from odoo import api, fields, models


class SedarInterviewScheduleWizard(models.TransientModel):
    _name = 'sedar.interview.schedule.wizard'
    _description = 'Schedule Applicant Interview'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade')
    interview_datetime = fields.Datetime(required=True)
    interview_mode = fields.Selection(
        [('online', 'Online'), ('face_to_face', 'Face to Face')],
        required=True,
        default='face_to_face',
    )
    interview_location = fields.Char(string='Interview Link / Venue')
    note = fields.Text(string='HR Note')
    occupied_dates_html = fields.Html(
        string='Occupied Interview Dates',
        compute='_compute_occupied_dates_html',
        sanitize=False,
    )
    selected_day_warning = fields.Html(
        string='Selected Day Availability',
        compute='_compute_selected_day_warning',
        sanitize=False,
    )

    def _get_upcoming_interviews(self):
        domain = [
            ('sedar_hiring_state', '=', 'for_interview'),
            ('sedar_interview_datetime', '!=', False),
        ]
        if self.applicant_id:
            domain.append(('id', '!=', self.applicant_id.id))
        return self.env['hr.applicant'].search(domain, order='sedar_interview_datetime asc')

    @api.depends('applicant_id')
    def _compute_occupied_dates_html(self):
        for wizard in self:
            interviews = wizard._get_upcoming_interviews()
            if not interviews:
                wizard.occupied_dates_html = Markup(
                    '<div class="o_sedar_interview_notice o_sedar_interview_notice_empty">'
                    'No scheduled interviews yet. Any day is currently open.'
                    '</div>'
                )
                continue

            grouped = {}
            for applicant in interviews:
                local_dt = fields.Datetime.context_timestamp(wizard, applicant.sedar_interview_datetime)
                key = local_dt.date()
                grouped.setdefault(key, []).append((local_dt, applicant))

            items = []
            for day, day_interviews in grouped.items():
                details = ''.join(
                    '<li><strong>{time}</strong> - {name}</li>'.format(
                        time=escape(local_dt.strftime('%I:%M %p')),
                        name=escape(applicant.display_name),
                    )
                    for local_dt, applicant in day_interviews
                )
                items.append(
                    '<div class="o_sedar_interview_day">'
                    '<div class="o_sedar_interview_day_badge">{day}<span>{count}</span></div>'
                    '<ul>{details}</ul>'
                    '</div>'.format(
                        day=escape(day.strftime('%b %d')),
                        count=escape(str(len(day_interviews))),
                        details=details,
                    )
                )

            wizard.occupied_dates_html = Markup(
                '<div class="o_sedar_interview_occupied">'
                '<div class="o_sedar_interview_occupied_title">Already Scheduled</div>'
                '{items}'
                '</div>'.format(items=''.join(items))
            )

    @api.depends('applicant_id', 'interview_datetime')
    def _compute_selected_day_warning(self):
        for wizard in self:
            if not wizard.interview_datetime:
                wizard.selected_day_warning = False
                continue

            selected_dt = fields.Datetime.context_timestamp(wizard, wizard.interview_datetime)
            selected_day = selected_dt.date()
            matches = []
            for applicant in wizard._get_upcoming_interviews():
                local_dt = fields.Datetime.context_timestamp(wizard, applicant.sedar_interview_datetime)
                if local_dt.date() == selected_day:
                    matches.append((local_dt, applicant))

            if not matches:
                wizard.selected_day_warning = Markup(
                    '<div class="o_sedar_interview_notice o_sedar_interview_notice_free">'
                    'This day has no scheduled interviews yet.'
                    '</div>'
                )
                continue

            details = ''.join(
                '<li><strong>{time}</strong> - {name}</li>'.format(
                    time=escape(local_dt.strftime('%I:%M %p')),
                    name=escape(applicant.display_name),
                )
                for local_dt, applicant in matches
            )
            wizard.selected_day_warning = Markup(
                '<div class="o_sedar_interview_notice o_sedar_interview_notice_busy">'
                '<strong>This day already has {count} interview(s):</strong>'
                '<ul>{details}</ul>'
                '</div>'.format(count=escape(str(len(matches))), details=details)
            )

    def action_schedule(self):
        self.ensure_one()
        values = {
            'sedar_hiring_state': 'for_interview',
            'sedar_interview_datetime': self.interview_datetime,
            'sedar_interview_mode': self.interview_mode,
            'sedar_interview_location': self.interview_location,
        }
        if self.note:
            values['description'] = ((self.applicant_id.description or '') + '\n\nInterview Note: ' + self.note).strip()
        self.applicant_id.write(values)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pending Interviews',
            'res_model': 'hr.applicant',
            'view_mode': 'calendar,tree,form',
            'domain': [('sedar_hiring_state', '=', 'for_interview')],
            'context': {'default_sedar_hiring_state': 'for_interview', 'calendar_default_mode': 'month'},
        }

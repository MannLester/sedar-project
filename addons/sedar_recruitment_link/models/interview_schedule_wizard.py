from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SedarInterviewScheduleWizard(models.TransientModel):
    _name = 'sedar.interview.schedule.wizard'
    _description = 'Schedule Applicant Interview'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade')
    interview_datetime = fields.Datetime(required=True)
    interview_duration = fields.Float(
        string='Duration',
        required=True,
        default=1.0,
        help='Duration in hours.',
    )
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
    available_slots_html = fields.Html(
        string='Available Slots',
        compute='_compute_available_slots_html',
        sanitize=False,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        applicant_id = values.get('applicant_id') or self.env.context.get('default_applicant_id')
        interview_duration = values.get('interview_duration') or self.env.context.get('default_interview_duration') or 1.0
        if applicant_id and not values.get('interview_datetime'):
            applicant = self.env['hr.applicant'].browse(applicant_id)
            if applicant.exists():
                interview_datetime = applicant.sedar_interview_datetime or applicant._sedar_next_interview_slot(
                    interview_duration
                )
                values['interview_datetime'] = fields.Datetime.to_string(interview_datetime)
        return values

    def _get_upcoming_interviews(self):
        domain = [
            ('sedar_hiring_state', '=', 'for_interview'),
            ('sedar_interview_datetime', '!=', False),
        ]
        if self.applicant_id:
            domain.append(('id', '!=', self.applicant_id.id))
        return self.env['hr.applicant'].search(domain, order='sedar_interview_datetime asc')

    def _get_selected_day_interviews(self):
        self.ensure_one()
        if not self.interview_datetime:
            return []

        selected_dt = fields.Datetime.context_timestamp(self, self.interview_datetime)
        selected_day = selected_dt.date()
        matches = []
        for applicant in self._get_upcoming_interviews():
            local_start = fields.Datetime.context_timestamp(self, applicant.sedar_interview_datetime)
            if local_start.date() != selected_day:
                continue
            local_end = fields.Datetime.context_timestamp(self, applicant.sedar_interview_end)
            matches.append((local_start, local_end, applicant))
        return matches

    def _format_local_range(self, local_start, local_end):
        return '%s - %s' % (local_start.strftime('%I:%M %p'), local_end.strftime('%I:%M %p'))

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
                local_end = fields.Datetime.context_timestamp(wizard, applicant.sedar_interview_end)
                key = local_dt.date()
                grouped.setdefault(key, []).append((local_dt, local_end, applicant))

            items = []
            for day, day_interviews in grouped.items():
                details = ''.join(
                    '<li><strong>{time}</strong> - {name}</li>'.format(
                        time=escape(wizard._format_local_range(local_dt, local_end)),
                        name=escape(applicant.display_name),
                    )
                    for local_dt, local_end, applicant in day_interviews
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

            matches = wizard._get_selected_day_interviews()

            if not matches:
                wizard.selected_day_warning = Markup(
                    '<div class="o_sedar_interview_notice o_sedar_interview_notice_free">'
                    'This day has no scheduled interviews yet.'
                    '</div>'
                )
                continue

            details = ''.join(
                '<li><strong>{time}</strong> - {name}</li>'.format(
                    time=escape(wizard._format_local_range(local_dt, local_end)),
                    name=escape(applicant.display_name),
                )
                for local_dt, local_end, applicant in matches
            )
            wizard.selected_day_warning = Markup(
                '<div class="o_sedar_interview_notice o_sedar_interview_notice_busy">'
                '<strong>This day already has {count} interview(s):</strong>'
                '<ul>{details}</ul>'
                '</div>'.format(count=escape(str(len(matches))), details=details)
            )

    @api.depends('applicant_id', 'interview_datetime', 'interview_duration')
    def _compute_available_slots_html(self):
        for wizard in self:
            if not wizard.interview_datetime:
                wizard.available_slots_html = Markup(
                    '<div class="o_sedar_interview_notice o_sedar_interview_notice_empty">'
                    'Choose an interview date and time to see open slots for that day.'
                    '</div>'
                )
                continue
            if not wizard.interview_duration or wizard.interview_duration <= 0:
                wizard.available_slots_html = Markup(
                    '<div class="o_sedar_interview_notice o_sedar_interview_notice_busy">'
                    'Set a positive duration to calculate open slots.'
                    '</div>'
                )
                continue

            selected_dt = fields.Datetime.context_timestamp(wizard, wizard.interview_datetime)
            selected_day = selected_dt.date()
            occupied = wizard._get_selected_day_interviews()
            slots = []
            start_hour = 8
            end_hour = 17
            step_minutes = 30
            duration_minutes = int(round(wizard.interview_duration * 60))

            cursor = selected_dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_end = selected_dt.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            while cursor.date() == selected_day and fields.Datetime.add(cursor, minutes=duration_minutes) <= day_end:
                slot_end = fields.Datetime.add(cursor, minutes=duration_minutes)
                has_conflict = any(cursor < occupied_end and slot_end > occupied_start for occupied_start, occupied_end, applicant in occupied)
                if not has_conflict:
                    slots.append(wizard._format_local_range(cursor, slot_end))
                cursor = fields.Datetime.add(cursor, minutes=step_minutes)

            if slots:
                slot_items = ''.join('<span>{slot}</span>'.format(slot=escape(slot)) for slot in slots[:12])
                hidden_count = max(len(slots) - 12, 0)
                more = '<small>+{count} more</small>'.format(count=escape(str(hidden_count))) if hidden_count else ''
                wizard.available_slots_html = Markup(
                    '<div class="o_sedar_interview_slots">'
                    '<div class="o_sedar_interview_occupied_title">Open slots on {day}</div>'
                    '<div class="o_sedar_interview_slot_grid">{slots}{more}</div>'
                    '</div>'.format(
                        day=escape(selected_day.strftime('%b %d')),
                        slots=slot_items,
                        more=more,
                    )
                )
            else:
                wizard.available_slots_html = Markup(
                    '<div class="o_sedar_interview_notice o_sedar_interview_notice_busy">'
                    'No open slots remain between 8:00 AM and 5:00 PM for this duration.'
                    '</div>'
                )

    def action_schedule(self):
        self.ensure_one()
        if not self.interview_duration or self.interview_duration <= 0:
            raise ValidationError(_('Set a positive interview duration.'))
        if not self.interview_location:
            raise ValidationError(_('Set the interview link or venue before scheduling the interview.'))

        conflict = self.applicant_id._sedar_find_interview_conflict(
            self.interview_datetime,
            self.interview_duration,
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

        values = {
            'sedar_hiring_state': 'for_interview',
            'sedar_interview_datetime': self.interview_datetime,
            'sedar_interview_duration': self.interview_duration,
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
            'view_mode': 'kanban,tree,calendar,form',
            'domain': [('sedar_hiring_state', '=', 'for_interview')],
            'context': {'default_sedar_hiring_state': 'for_interview', 'calendar_default_mode': 'week'},
        }

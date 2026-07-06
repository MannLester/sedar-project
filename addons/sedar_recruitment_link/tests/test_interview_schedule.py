from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestInterviewSchedule(TransactionCase):

    def _create_applicant(self, name, **values):
        data = {'name': name, 'partner_name': name}
        data.update(values)
        return self.env['hr.applicant'].create(data)

    def test_move_to_interview_opens_schedule_wizard(self):
        applicant = self._create_applicant('Schedule Wizard Applicant')

        action = applicant.action_sedar_for_interview()

        self.assertEqual(action['res_model'], 'sedar.interview.schedule.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_applicant_id'], applicant.id)
        self.assertTrue(action['context']['default_interview_datetime'])

    def test_for_interview_requires_schedule_details(self):
        applicant = self._create_applicant('Missing Schedule Applicant')

        with self.assertRaises(ValidationError):
            applicant.write({'sedar_hiring_state': 'for_interview'})

    def test_schedule_wizard_moves_applicant_to_pending_interviews(self):
        applicant = self._create_applicant('Interview Ready Applicant')
        schedule_at = fields.Datetime.to_datetime('2026-07-10 10:00:00')
        wizard = self.env['sedar.interview.schedule.wizard'].create({
            'applicant_id': applicant.id,
            'interview_datetime': schedule_at,
            'interview_duration': 1.5,
            'interview_mode': 'face_to_face',
            'interview_location': 'SEDAR HR Office',
        })

        action = wizard.action_schedule()

        self.assertEqual(applicant.sedar_hiring_state, 'for_interview')
        self.assertEqual(applicant.sedar_interview_datetime, schedule_at)
        self.assertEqual(applicant.sedar_interview_duration, 1.5)
        self.assertEqual(applicant.sedar_interview_end, fields.Datetime.to_datetime('2026-07-10 11:30:00'))
        self.assertEqual(action['name'], 'Pending Interviews')

    def test_schedule_wizard_blocks_overlapping_interview(self):
        schedule_at = fields.Datetime.to_datetime('2026-07-11 10:00:00')
        self._create_applicant(
            'Existing Interview Applicant',
            sedar_hiring_state='for_interview',
            sedar_interview_datetime=schedule_at,
            sedar_interview_duration=1.0,
            sedar_interview_mode='online',
            sedar_interview_location='Microsoft Teams',
        )
        applicant = self._create_applicant('Overlapping Interview Applicant')
        wizard = self.env['sedar.interview.schedule.wizard'].create({
            'applicant_id': applicant.id,
            'interview_datetime': fields.Datetime.to_datetime('2026-07-11 10:30:00'),
            'interview_duration': 1.0,
            'interview_mode': 'face_to_face',
            'interview_location': 'SEDAR HR Office',
        })

        with self.assertRaises(ValidationError):
            wizard.action_schedule()

    def test_calendar_resize_updates_interview_duration(self):
        applicant = self._create_applicant(
            'Resizable Interview Applicant',
            sedar_hiring_state='for_interview',
            sedar_interview_datetime=fields.Datetime.to_datetime('2026-07-12 10:00:00'),
            sedar_interview_duration=1.0,
            sedar_interview_mode='online',
            sedar_interview_location='Microsoft Teams',
        )

        applicant.write({'sedar_interview_end': fields.Datetime.to_datetime('2026-07-12 12:30:00')})

        self.assertEqual(applicant.sedar_interview_duration, 2.5)
        self.assertEqual(applicant.sedar_interview_end, fields.Datetime.to_datetime('2026-07-12 12:30:00'))

    def test_calendar_resize_blocks_overlap(self):
        self._create_applicant(
            'Later Interview Applicant',
            sedar_hiring_state='for_interview',
            sedar_interview_datetime=fields.Datetime.to_datetime('2026-07-13 11:00:00'),
            sedar_interview_duration=1.0,
            sedar_interview_mode='online',
            sedar_interview_location='Microsoft Teams',
        )
        applicant = self._create_applicant(
            'Resize Conflict Applicant',
            sedar_hiring_state='for_interview',
            sedar_interview_datetime=fields.Datetime.to_datetime('2026-07-13 10:00:00'),
            sedar_interview_duration=1.0,
            sedar_interview_mode='face_to_face',
            sedar_interview_location='SEDAR HR Office',
        )

        with self.assertRaises(ValidationError):
            applicant.write({'sedar_interview_end': fields.Datetime.to_datetime('2026-07-13 11:30:00')})

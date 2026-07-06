from odoo.tests.common import TransactionCase


class TestTugSchedule(TransactionCase):

    def test_schedule_workflow(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Masikap'})
        schedule = self.env['sedar.tug.schedule'].create({
            'name': 'Batangas standby window',
            'vessel_id': vessel.id,
            'port_area': 'Batangas Port',
            'assignment_type': 'standby',
        })
        self.assertEqual(schedule.state, 'planned')
        schedule.action_confirm()
        self.assertEqual(schedule.state, 'confirmed')
        schedule.action_start()
        self.assertEqual(schedule.state, 'in_progress')
        schedule.action_done()
        self.assertEqual(schedule.state, 'done')

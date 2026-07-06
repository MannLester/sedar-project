from odoo.tests.common import TransactionCase


class TestMaintenanceLink(TransactionCase):

    def test_equipment_linked_to_vessel(self):
        vessel = self.env['sedar.vessel'].create({'name': 'SEDAR Bagwis'})
        equipment = self.env['maintenance.equipment'].create({
            'name': 'Main Engine - Port',
            'vessel_id': vessel.id,
        })
        self.assertEqual(equipment.vessel_id, vessel)

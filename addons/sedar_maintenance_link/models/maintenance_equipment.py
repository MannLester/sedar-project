from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    vessel_id = fields.Many2one('sedar.vessel', string='Vessel')

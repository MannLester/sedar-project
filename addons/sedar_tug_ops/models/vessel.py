from odoo import fields, models


class SedarVessel(models.Model):
    _name = 'sedar.vessel'
    _description = 'Tugboat / Barge Vessel'
    _order = 'name'

    name = fields.Char(required=True)
    registry_no = fields.Char(string='IMO/Registry No.')
    vessel_type = fields.Selection(
        [('tug', 'Tug'), ('barge', 'Barge')],
        required=True,
        default='tug',
    )
    capacity = fields.Float(string='Capacity (BHP/DWT)')
    status = fields.Selection(
        [('active', 'Active'), ('dry_dock', 'Dry Dock'), ('standby', 'Standby')],
        default='active',
        required=True,
    )

from odoo import fields, models


class SedarCrewRotation(models.Model):
    _name = 'sedar.crew.rotation'
    _description = 'Crew Rotation Schedule'
    _order = 'onboard_date desc'

    crew_id = fields.Many2one('sedar.crew.member', string='Crew Member', required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', required=True)
    onboard_date = fields.Date(required=True)
    offboard_date = fields.Date()
    state = fields.Selection(
        [('planned', 'Planned'), ('onboard', 'On Board'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        default='planned',
        string='Rotation Status',
        required=True,
    )

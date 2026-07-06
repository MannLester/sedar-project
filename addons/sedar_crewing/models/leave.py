from odoo import fields, models


class SedarCrewLeave(models.Model):
    _name = 'sedar.crew.leave'
    _description = 'Crew Leave'
    _order = 'date_from desc'

    crew_id = fields.Many2one('sedar.crew.member', string='Crew Member', required=True)
    leave_type = fields.Selection(
        [('annual', 'Annual'), ('sick', 'Sick'), ('shore', 'Shore Leave'), ('other', 'Other')],
        default='annual',
        required=True,
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='draft',
        string='Approval Status',
        required=True,
    )

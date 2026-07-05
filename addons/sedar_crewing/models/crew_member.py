from odoo import fields, models


class SedarCrewMember(models.Model):
    _name = 'sedar.crew.member'
    _description = 'Crew Member'
    _order = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    name = fields.Char(related='employee_id.name', store=True, readonly=True)
    rank = fields.Char(string='Rank/Position', required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Current Vessel')
    payroll_reference = fields.Char(string='Payroll Reference')

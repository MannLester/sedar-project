from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sedar_crew_member_id = fields.Many2one(
        'sedar.crew.member',
        compute='_compute_sedar_crew_context',
        string='Crew Record',
    )
    sedar_current_vessel_id = fields.Many2one(
        'sedar.vessel',
        compute='_compute_sedar_crew_context',
        string='Current Boat',
    )
    sedar_crew_rank = fields.Char(
        compute='_compute_sedar_crew_context',
        string='Rank/Position',
    )
    sedar_payroll_reference = fields.Char(
        compute='_compute_sedar_crew_context',
        string='Payroll Reference',
    )

    @api.depends('name')
    def _compute_sedar_crew_context(self):
        crew_by_employee = {}
        if self.ids:
            crew_members = self.env['sedar.crew.member'].search([
                ('employee_id', 'in', self.ids),
            ])
            for crew in crew_members:
                crew_by_employee.setdefault(crew.employee_id.id, crew)

        for employee in self:
            crew = crew_by_employee.get(employee.id)
            employee.sedar_crew_member_id = crew
            employee.sedar_current_vessel_id = crew.vessel_id if crew else False
            employee.sedar_crew_rank = crew.rank if crew else employee.job_title
            employee.sedar_payroll_reference = crew.payroll_reference if crew else False

    def action_sedar_email_placeholder(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email'),
                'message': _('Email action placeholder for %s.') % self.name,
                'type': 'info',
                'sticky': False,
            },
        }


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    sedar_crew_member_id = fields.Many2one(
        'sedar.crew.member',
        compute='_compute_sedar_crew_context',
        string='Crew Record',
    )
    sedar_current_vessel_id = fields.Many2one(
        'sedar.vessel',
        compute='_compute_sedar_crew_context',
        string='Current Boat',
    )
    sedar_crew_rank = fields.Char(
        compute='_compute_sedar_crew_context',
        string='Rank/Position',
    )
    sedar_payroll_reference = fields.Char(
        compute='_compute_sedar_crew_context',
        string='Payroll Reference',
    )

    @api.depends('name')
    def _compute_sedar_crew_context(self):
        crew_by_employee = {}
        if self.ids:
            crew_members = self.env['sedar.crew.member'].search([
                ('employee_id', 'in', self.ids),
            ])
            for crew in crew_members:
                crew_by_employee.setdefault(crew.employee_id.id, crew)

        for employee in self:
            crew = crew_by_employee.get(employee.id)
            employee.sedar_crew_member_id = crew
            employee.sedar_current_vessel_id = crew.vessel_id if crew else False
            employee.sedar_crew_rank = crew.rank if crew else employee.job_title
            employee.sedar_payroll_reference = crew.payroll_reference if crew else False

    def action_sedar_email_placeholder(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email'),
                'message': _('Email action placeholder for %s.') % self.name,
                'type': 'info',
                'sticky': False,
            },
        }

import re

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sedar_employee_code = fields.Char(
        string='Employee ID',
        compute='_compute_sedar_identity',
        search='_search_sedar_employee_code',
    )
    sedar_barcode_value = fields.Char(
        string='Barcode Value',
        compute='_compute_sedar_identity',
        search='_search_sedar_employee_code',
    )

    def _compute_sedar_identity(self):
        for employee in self:
            code = employee._sedar_identity_code()
            employee.sedar_employee_code = code
            employee.sedar_barcode_value = code

    def _sedar_identity_code(self):
        self.ensure_one()
        return 'SEDAR-EMP-%05d' % self.id if self.id else False

    def _search_sedar_employee_code(self, operator, value):
        return self._sedar_identity_search_domain(operator, value)

    def _sedar_identity_search_domain(self, operator, value):
        supported_operators = {'=', 'ilike', '=ilike', 'like', '=like'}
        if operator not in supported_operators or not value:
            return [('id', '=', 0)]

        matches = re.findall(r'\d+', str(value))
        if not matches:
            return [('id', '=', 0)]

        employee_id = int(matches[-1])
        return [('id', '=', employee_id)]


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    sedar_employee_code = fields.Char(
        string='Employee ID',
        compute='_compute_sedar_identity',
        search='_search_sedar_employee_code',
    )
    sedar_barcode_value = fields.Char(
        string='Barcode Value',
        compute='_compute_sedar_identity',
        search='_search_sedar_employee_code',
    )

    def _compute_sedar_identity(self):
        for employee in self:
            code = 'SEDAR-EMP-%05d' % employee.id if employee.id else False
            employee.sedar_employee_code = code
            employee.sedar_barcode_value = code

    def action_sedar_print_employee_badge(self):
        return self.env.ref('sedar_employee_identity.action_sedar_employee_badge_report').report_action(self)

    def _search_sedar_employee_code(self, operator, value):
        return self.env['hr.employee']._sedar_identity_search_domain(operator, value)

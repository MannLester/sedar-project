from odoo import _, api, fields, models


class SedarJobDispatch(models.Model):
    _name = 'sedar.job.dispatch'
    _description = 'Crew Job Dispatch Order'
    _order = 'requested_datetime desc, id desc'

    name = fields.Char(default='New', copy=False, readonly=True, required=True)
    role_needed = fields.Char(string='Role to Hire', required=True)
    quantity = fields.Integer(default=1, required=True)
    vessel_id = fields.Many2one('sedar.vessel', string='Requesting Boat')
    client_name = fields.Char(string='Requesting Client')
    requested_datetime = fields.Datetime(default=fields.Datetime.now, required=True)
    needed_by = fields.Datetime(string='Needed By')
    missing_reason = fields.Text(string='Missing Role / Request Reason')
    requirements = fields.Text(string='Requirements')
    state = fields.Selection(
        [
            ('draft', 'For HR Review'),
            ('approved', 'Published for Applications'),
            ('filled', 'Filled'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
    )
    hr_job_id = fields.Many2one('hr.job', string='Published Job')
    applicant_ids = fields.One2many('hr.applicant', 'sedar_dispatch_id', string='Applicants')
    applicant_count = fields.Integer(compute='_compute_applicant_count')

    def _compute_applicant_count(self):
        for dispatch in self:
            dispatch.applicant_count = len(dispatch.applicant_ids)

    def action_approve_publish(self):
        for dispatch in self:
            job = dispatch.hr_job_id
            if not job:
                job = self.env['hr.job'].create({
                    'name': dispatch.role_needed,
                    'no_of_recruitment': dispatch.quantity,
                    'description': dispatch.requirements or dispatch.missing_reason or '',
                })
            publish_values = {}
            if 'website_published' in job._fields:
                publish_values['website_published'] = True
            if 'is_published' in job._fields:
                publish_values['is_published'] = True
            publish_values['no_of_recruitment'] = dispatch.quantity
            job.write(publish_values)
            dispatch.write({'state': 'approved', 'hr_job_id': job.id})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_mark_filled(self):
        self.write({'state': 'filled'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_view_applicants(self):
        self.ensure_one()
        return {
            'name': _('Applicants'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.applicant',
            'view_mode': 'tree,form',
            'domain': [('sedar_dispatch_id', '=', self.id)],
            'context': {
                'default_sedar_dispatch_id': self.id,
                'default_job_id': self.hr_job_id.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sedar.job.dispatch') or 'New'
        return super().create(vals_list)

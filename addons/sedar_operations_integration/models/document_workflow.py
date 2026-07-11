from odoo import api, fields, models
from odoo.exceptions import UserError


DEPARTMENTS = [
    ('management', 'Management'),
    ('finance', 'Finance and Accounting'),
    ('operations', 'Tug Operations'),
    ('technical', 'Technical and Maintenance'),
    ('hsse', 'HSSE'),
    ('crewing', 'Crewing'),
    ('procurement', 'Procurement'),
    ('hr', 'Human Resources'),
    ('document_control', 'Document Control'),
]


class SedarDocumentControl(models.Model):
    _name = 'sedar.document.control'
    _description = 'SEDAR Controlled Document'
    _order = 'expiry_date, name'

    name = fields.Char(required=True)
    document_type = fields.Selection(
        [
            ('contract', 'Contract'),
            ('vessel_certificate', 'Vessel Certificate'),
            ('insurance', 'Insurance'),
            ('permit', 'Permit'),
            ('board_resolution', 'Board Resolution'),
            ('iso_document', 'ISO Document'),
            ('other', 'Other'),
        ],
        default='other',
        required=True,
    )
    owner_department = fields.Selection(DEPARTMENTS, default='document_control', required=True)
    department = fields.Selection(related='owner_department', readonly=False, store=True)
    vessel_id = fields.Many2one('sedar.vessel')
    issue_date = fields.Date()
    expiry_date = fields.Date()
    status = fields.Selection(
        [('valid', 'Valid'), ('renewal', 'For Renewal'), ('expired', 'Expired')],
        default='valid',
        required=True,
    )
    version = fields.Char(default='1.0')
    document_link = fields.Char()
    approval_status = fields.Selection(
        [('draft', 'Draft'), ('for_review', 'For Review'), ('approved', 'Approved')],
        default='draft',
        required=True,
    )
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True, string='Document Owner')
    reviewer_id = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    renewal_owner = fields.Many2one('res.users', string='Renewal Owner')
    legacy_renewal_owner = fields.Char(readonly=True)
    approval_date = fields.Date(readonly=True, copy=False)
    previous_version_id = fields.Many2one('sedar.document.control', string='Previous Version', readonly=True, copy=False)
    renewal_due_date = fields.Date(compute='_compute_renewal_due_date', store=True)
    workflow_notes = fields.Text(string='Review Notes')
    attachment = fields.Binary(string='File Attachment')
    attachment_filename = fields.Char()

    @api.depends('expiry_date')
    def _compute_renewal_due_date(self):
        for document in self:
            document.renewal_due_date = fields.Date.subtract(document.expiry_date, days=30) if document.expiry_date else False

    def action_submit_review(self):
        for document in self:
            if not document.attachment:
                raise UserError('Attach the controlled document before submitting it for review.')
            if document.approval_status != 'draft':
                raise UserError('Only draft documents can be submitted for review.')
        self.write({'approval_status': 'for_review'})

    def action_approve_document(self):
        for document in self:
            if document.approval_status != 'for_review':
                raise UserError('Only documents under review can be approved.')
            if not document.attachment:
                raise UserError('The controlled document file is required for approval.')
        self.write({
            'approval_status': 'approved',
            'reviewer_id': self.env.user.id,
            'approval_date': fields.Date.context_today(self),
        })

    def action_reject_document(self):
        for document in self:
            if document.approval_status != 'for_review':
                raise UserError('Only documents under review can be returned to draft.')
            if not document.workflow_notes:
                raise UserError('Add review notes before returning the document to draft.')
        self.write({'approval_status': 'draft', 'reviewer_id': False, 'approval_date': False})

    def action_start_renewal(self):
        self.ensure_one()
        if self.approval_status != 'approved':
            raise UserError('Approve the current version before starting a renewal.')
        try:
            next_version = str(float(self.version or '1.0') + 1.0)
        except ValueError:
            next_version = '%s.1' % (self.version or '1')
        values = {
            'approval_status': 'draft',
            'version': next_version,
            'reviewer_id': False,
            'approval_date': False,
            'previous_version_id': self.id,
            'expiry_date': False,
            'workflow_notes': False,
            'attachment': False,
            'attachment_filename': False,
            'status': 'renewal',
        }
        renewed = self.copy(values)
        self.status = 'renewal'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': renewed.id,
            'view_mode': 'form',
            'target': 'current',
        }

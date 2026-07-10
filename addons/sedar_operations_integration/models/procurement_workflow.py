from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


DEPARTMENTS = [
    ('management', 'Management'),
    ('finance', 'Finance and Accounting'),
    ('operations', 'Tug Operations'),
    ('technical', 'Technical and Maintenance'),
    ('hsse', 'HSSE'),
    ('crewing', 'Crewing'),
    ('procurement', 'Procurement'),
    ('inventory', 'Inventory'),
    ('hr', 'Human Resources'),
]


class SedarPurchaseRequest(models.Model):
    _name = 'sedar.purchase.request'
    _description = 'Native-backed Purchase Request'
    _order = 'request_date desc, id desc'

    name = fields.Char(default='New', readonly=True, copy=False, required=True)
    request_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    needed_date = fields.Date(required=True)
    requested_by_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True, index=True)
    department = fields.Selection(DEPARTMENTS, required=True)
    priority = fields.Selection(
        [('normal', 'Normal'), ('urgent', 'Urgent'), ('critical', 'Critical')],
        default='normal',
        required=True,
    )
    purpose = fields.Text(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)
    vessel_id = fields.Many2one('sedar.vessel', index=True)
    job_order_id = fields.Many2one('sedar.job.order', index=True)
    maintenance_request_id = fields.Many2one('maintenance.request', index=True)
    budget_id = fields.Many2one('sedar.finance.budget', check_company=True, index=True)
    preferred_vendor_id = fields.Many2one('res.partner', domain=[('supplier_rank', '>', 0)])
    line_ids = fields.One2many('sedar.purchase.request.line', 'request_id', copy=True)
    estimated_total = fields.Monetary(compute='_compute_estimated_total', store=True)
    purchase_order_ids = fields.One2many('purchase.order', 'sedar_purchase_request_id')
    approver_id = fields.Many2one('res.users', readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(copy=False)
    history_ids = fields.One2many('sedar.purchase.approval.history', 'request_id', readonly=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('rfq_created', 'RFQ Created'),
            ('ordered', 'Ordered'),
            ('received', 'Received'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('name', 'New') == 'New':
                values['name'] = self.env['ir.sequence'].next_by_code('sedar.purchase.request') or 'New'
        return super().create(values_list)

    @api.depends('line_ids.subtotal')
    def _compute_estimated_total(self):
        for request in self:
            request.estimated_total = sum(request.line_ids.mapped('subtotal'))

    @api.constrains('request_date', 'needed_date')
    def _check_request_dates(self):
        for request in self:
            if request.needed_date < request.request_date:
                raise ValidationError('The needed date cannot be before the request date.')

    @api.onchange('job_order_id')
    def _onchange_job_order_id(self):
        if self.job_order_id:
            self.vessel_id = self.job_order_id.vessel_id

    @api.onchange('maintenance_request_id')
    def _onchange_maintenance_request_id(self):
        if self.maintenance_request_id:
            self.vessel_id = self.maintenance_request_id.vessel_id

    def _add_history(self, action, note=False):
        self.ensure_one()
        self.env['sedar.purchase.approval.history'].sudo().create({
            'request_id': self.id,
            'action': action,
            'user_id': self.env.user.id,
            'note': note,
        })

    def action_submit(self):
        for request in self:
            if request.state != 'draft':
                raise UserError('Only draft purchase requests can be submitted.')
            if not request.line_ids:
                raise UserError('Add at least one product line before submitting the request.')
            request.write({'state': 'submitted', 'rejection_reason': False})
            request._add_history('submitted')
        return True

    def action_approve(self):
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError('Only a Purchase Manager can approve purchase requests.')
        for request in self:
            if request.state != 'submitted':
                raise UserError('Only submitted purchase requests can be approved.')
            request._check_budget_available()
            request.write({
                'state': 'approved',
                'approver_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
                'rejection_reason': False,
            })
            request._add_history('approved')
        return True

    def action_reject(self):
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError('Only a Purchase Manager can reject purchase requests.')
        for request in self:
            if request.state != 'submitted':
                raise UserError('Only submitted purchase requests can be rejected.')
            if not request.rejection_reason:
                raise UserError('Enter the rejection reason before rejecting the request.')
            request.write({'state': 'rejected', 'approver_id': self.env.user.id, 'approval_date': fields.Datetime.now()})
            request._add_history('rejected', request.rejection_reason)
        return True

    def action_reset_draft(self):
        for request in self:
            if request.state != 'rejected':
                raise UserError('Only rejected purchase requests can return to draft.')
            request.write({'state': 'draft', 'approver_id': False, 'approval_date': False})
            request._add_history('reset')
        return True

    def action_cancel(self):
        for request in self:
            if request.purchase_order_ids.filtered(lambda order: order.state in ('purchase', 'done')):
                raise UserError('A purchase request with a confirmed purchase order cannot be cancelled.')
            request.state = 'cancelled'
            request._add_history('cancelled')
        return True

    def _check_budget_available(self):
        self.ensure_one()
        if not self.budget_id:
            return
        if self.budget_id.state != 'approved':
            raise UserError('Select an approved department budget before approving this request.')
        amount = self.currency_id._convert(
            self.estimated_total,
            self.budget_id.currency_id,
            self.company_id,
            self.request_date,
        )
        if self.budget_id.currency_id.compare_amounts(amount, self.budget_id.available_amount) > 0:
            raise UserError('The estimated request total is greater than the available department budget.')

    def action_create_rfq(self):
        self.ensure_one()
        if self.state not in ('approved', 'rfq_created'):
            raise UserError('Approve the purchase request before creating an RFQ.')
        active_order = self.purchase_order_ids.filtered(lambda order: order.state != 'cancel')[:1]
        if active_order:
            return active_order
        if not self.preferred_vendor_id:
            raise UserError('Select an accredited preferred supplier before creating an RFQ.')
        if self.preferred_vendor_id.sedar_supplier_accreditation != 'approved':
            raise UserError('The preferred supplier must be accredited before creating an RFQ.')

        purchase_currency = self.env.ref('base.PHP', raise_if_not_found=False) or self.currency_id
        order = self.env['purchase.order'].create({
            'partner_id': self.preferred_vendor_id.id,
            'origin': self.name,
            'currency_id': purchase_currency.id,
            'sedar_purchase_request_id': self.id,
            'sedar_job_order_id': self.job_order_id.id,
            'sedar_vessel_id': self.vessel_id.id,
            'sedar_maintenance_request_id': self.maintenance_request_id.id,
            'sedar_budget_id': self.budget_id.id,
            'sedar_budget_amount': self.currency_id._convert(
                self.budget_id.available_amount,
                purchase_currency,
                self.company_id,
                self.request_date,
            ) if self.budget_id else 0.0,
            'order_line': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.description or line.product_id.display_name,
                    'product_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'price_unit': self.currency_id._convert(
                        line.estimated_unit_price,
                        purchase_currency,
                        self.company_id,
                        self.request_date,
                    ),
                    'date_planned': fields.Datetime.to_datetime(self.needed_date),
                })
                for line in self.line_ids
            ],
        })
        self.state = 'rfq_created'
        self._add_history('rfq_created', order.name)
        return order


class SedarPurchaseRequestLine(models.Model):
    _name = 'sedar.purchase.request.line'
    _description = 'Purchase Request Product Line'
    _order = 'request_id, id'

    request_id = fields.Many2one('sedar.purchase.request', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', required=True, domain=[('purchase_ok', '=', True)])
    description = fields.Char()
    quantity = fields.Float(default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', required=True)
    estimated_unit_price = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='request_id.currency_id', store=True, readonly=True)
    subtotal = fields.Monetary(compute='_compute_subtotal', store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.uom_id = self.product_id.uom_po_id
            self.estimated_unit_price = self.product_id.standard_price

    @api.depends('quantity', 'estimated_unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.estimated_unit_price

    @api.constrains('quantity', 'estimated_unit_price')
    def _check_line_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError('Purchase request quantity must be greater than zero.')
            if line.estimated_unit_price < 0:
                raise ValidationError('Estimated unit price cannot be negative.')


class SedarPurchaseApprovalHistory(models.Model):
    _name = 'sedar.purchase.approval.history'
    _description = 'Purchase Request Approval History'
    _order = 'action_date desc, id desc'

    request_id = fields.Many2one('sedar.purchase.request', required=True, ondelete='cascade', index=True)
    action = fields.Selection(
        [
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('reset', 'Reset to Draft'),
            ('rfq_created', 'RFQ Created'),
            ('ordered', 'Ordered'),
            ('received', 'Received'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
    )
    user_id = fields.Many2one('res.users', required=True)
    action_date = fields.Datetime(default=fields.Datetime.now, required=True)
    note = fields.Text()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sedar_purchase_request_id = fields.Many2one('sedar.purchase.request', copy=False, index=True)

    def button_confirm(self):
        for order in self.filtered('sedar_purchase_request_id'):
            if order.partner_id.sedar_supplier_accreditation != 'approved':
                raise UserError('The purchase request supplier must be accredited before confirming the order.')
        result = super().button_confirm()
        for order in self.filtered(lambda item: item.sedar_purchase_request_id.state == 'rfq_created'):
            order.sedar_purchase_request_id.state = 'ordered'
            order.sedar_purchase_request_id._add_history('ordered', order.name)
        return result

    def button_cancel(self):
        requests = self.mapped('sedar_purchase_request_id')
        result = super().button_cancel()
        for request in requests.filtered(lambda item: item.state in ('rfq_created', 'ordered')):
            if not request.purchase_order_ids.filtered(lambda order: order.state != 'cancel'):
                request.state = 'approved'
        return result


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        result = super().button_validate()
        requests = self.filtered(lambda picking: picking.state == 'done').mapped(
            'purchase_id.sedar_purchase_request_id'
        )
        for request in requests.filtered(lambda item: item.state == 'ordered'):
            purchase_pickings = request.purchase_order_ids.mapped('picking_ids').filtered(
                lambda picking: picking.state != 'cancel'
            )
            if purchase_pickings and all(picking.state == 'done' for picking in purchase_pickings):
                request.state = 'received'
                request._add_history('received')
        return result

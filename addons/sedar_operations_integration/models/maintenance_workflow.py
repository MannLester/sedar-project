from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    vessel_id = fields.Many2one('sedar.vessel', string='Vessel', index=True)


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    def _default_sedar_currency(self):
        return self.env.ref('base.PHP', raise_if_not_found=False) or self.env.company.currency_id

    vessel_id = fields.Many2one(
        'sedar.vessel',
        related='equipment_id.vessel_id',
        store=True,
        readonly=True,
        index=True,
    )
    severity = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='medium',
        required=True,
    )
    blocks_operation = fields.Boolean(string='Blocks Vessel Operation')
    downtime_hours = fields.Float()
    estimated_cost = fields.Monetary(currency_field='currency_id')
    actual_cost = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=_default_sedar_currency)
    is_dry_dock = fields.Boolean(string='Dry Dock Work')
    dry_dock_start = fields.Date()
    dry_dock_end = fields.Date()
    preferred_vendor_id = fields.Many2one('res.partner', domain=[('supplier_rank', '>', 0)])
    part_line_ids = fields.One2many('sedar.maintenance.part.line', 'maintenance_request_id', string='Required Parts')
    parts_ready = fields.Boolean(compute='_compute_sedar_counts', string='Parts Ready')
    shortage_count = fields.Integer(compute='_compute_sedar_counts')
    purchase_order_ids = fields.One2many('purchase.order', 'sedar_maintenance_request_id', string='RFQs and Purchase Orders')
    purchase_order_count = fields.Integer(compute='_compute_sedar_counts')
    sedar_can_start = fields.Boolean(compute='_compute_sedar_counts')
    sedar_can_complete = fields.Boolean(compute='_compute_sedar_counts')
    sedar_can_buy_parts = fields.Boolean(compute='_compute_sedar_counts')

    @api.depends('part_line_ids', 'part_line_ids.shortage_qty', 'purchase_order_ids', 'stage_id', 'done', 'archive')
    def _compute_sedar_counts(self):
        in_progress = self.env.ref('maintenance.stage_1', raise_if_not_found=False)
        for request in self:
            shortages = request.part_line_ids.filtered(lambda line: line.shortage_qty > 0)
            request.parts_ready = not shortages
            request.shortage_count = len(shortages)
            request.purchase_order_count = len(request.purchase_order_ids)
            request.sedar_can_start = not request.done and not request.archive and not shortages and request.stage_id != in_progress
            request.sedar_can_complete = not request.done and request.stage_id == in_progress
            request.sedar_can_buy_parts = not request.done and not request.archive and bool(shortages)

    @api.constrains('is_dry_dock', 'dry_dock_start', 'dry_dock_end')
    def _check_dry_dock_dates(self):
        for request in self:
            if request.is_dry_dock and request.dry_dock_start and request.dry_dock_end:
                if request.dry_dock_end < request.dry_dock_start:
                    raise ValidationError('Dry dock end date cannot be before the start date.')

    def action_waiting_parts(self):
        stage = self.env.ref('sedar_operations_integration.maintenance_stage_waiting_parts')
        self.write({'stage_id': stage.id})

    def action_start_sedar(self):
        stage = self.env.ref('maintenance.stage_1')
        for request in self:
            if request.done or request.archive:
                raise UserError('Reopen this work order before starting it.')
            if not request.parts_ready:
                raise UserError('Required parts are short. Create and receive the linked RFQ before starting work.')
            if request.is_dry_dock and (not request.dry_dock_start or not request.dry_dock_end):
                raise UserError('Set the dry dock start and end dates before starting work.')
        self.write({'stage_id': stage.id})

    def action_complete_sedar(self):
        repaired = self.env.ref('maintenance.stage_3')
        in_progress = self.env.ref('maintenance.stage_1')
        for request in self:
            if request.stage_id != in_progress:
                raise UserError('Start the work order before marking it complete.')
        self.write({'stage_id': repaired.id, 'close_date': fields.Date.context_today(self)})

    def action_create_rfq(self):
        self.ensure_one()
        if self.done or self.archive:
            raise UserError('Reopen this work order before creating an RFQ.')
        shortages = self.part_line_ids.filtered(lambda line: line.shortage_qty > 0)
        if not shortages:
            raise UserError('There are no part shortages to purchase.')
        if not self.preferred_vendor_id:
            raise UserError('Select a preferred vendor before creating an RFQ.')
        existing = self.purchase_order_ids.filtered(lambda order: order.state in ('draft', 'sent'))
        if existing:
            return self._open_purchase_order(existing[0])
        order = self.env['purchase.order'].create({
            'partner_id': self.preferred_vendor_id.id,
            'origin': self.name,
            'sedar_maintenance_request_id': self.id,
            'sedar_vessel_id': self.vessel_id.id,
            'sedar_inventory_product_id': shortages[0].product_id.id,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': '%s - %s' % (self.name, line.product_id.display_name),
                'product_qty': line.shortage_qty,
                'product_uom': line.product_id.uom_po_id.id,
                'price_unit': line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            }) for line in shortages],
        })
        self.action_waiting_parts()
        return self._open_purchase_order(order)

    def _open_purchase_order(self, order):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance RFQ',
            'res_model': 'purchase.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance RFQs and Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('sedar_maintenance_request_id', '=', self.id)],
            'context': {'default_sedar_maintenance_request_id': self.id, 'default_sedar_vessel_id': self.vessel_id.id},
        }


class SedarMaintenancePartLine(models.Model):
    _name = 'sedar.maintenance.part.line'
    _description = 'Maintenance Required Part'
    _order = 'maintenance_request_id, id'

    maintenance_request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True, domain=[('purchase_ok', '=', True)])
    required_qty = fields.Float(default=1.0, required=True)
    available_qty = fields.Float(related='product_id.qty_available', string='Available', readonly=True)
    shortage_qty = fields.Float(compute='_compute_shortage', string='Shortage')
    product_uom_id = fields.Many2one(related='product_id.uom_id', string='Unit', readonly=True)

    @api.depends('required_qty', 'available_qty')
    def _compute_shortage(self):
        for line in self:
            line.shortage_qty = max(line.required_qty - line.available_qty, 0.0)

    @api.constrains('required_qty')
    def _check_required_qty(self):
        if any(line.required_qty <= 0 for line in self):
            raise ValidationError('Required part quantity must be greater than zero.')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sedar_maintenance_request_id = fields.Many2one('maintenance.request', string='Community Maintenance Work Order', copy=False)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sedar_maintenance_request_id = fields.Many2one(
        'maintenance.request',
        related='purchase_id.sedar_maintenance_request_id',
        store=True,
        string='Maintenance Work Order',
    )


class SedarJobOrder(models.Model):
    _inherit = 'sedar.job.order'

    maintenance_count = fields.Integer(compute='_compute_maintenance_count')

    def _compute_readiness(self):
        super()._compute_readiness()
        now = fields.Datetime.now()
        for job in self:
            if not job.vessel_id:
                continue
            requests = self.env['maintenance.request'].search([
                ('vessel_id', '=', job.vessel_id.id),
                ('done', '=', False),
                ('archive', '=', False),
            ])
            blockers = requests.filtered(lambda request: request.blocks_operation or request.severity == 'critical')
            overdue = requests.filtered(lambda request: request.schedule_date and request.schedule_date < now and request not in blockers)
            notes = [] if job.readiness_state == 'ready' else [job.readiness_note.rstrip('.')]
            if blockers:
                notes.append('%s blocking maintenance work order(s)' % len(blockers))
                job.readiness_state = 'not_ready'
            elif overdue and job.readiness_state == 'ready':
                notes.append('%s overdue maintenance work order(s)' % len(overdue))
                job.readiness_state = 'warning'
            if notes:
                job.readiness_note = '. '.join(notes) + '.'

    def _compute_maintenance_count(self):
        for job in self:
            job.maintenance_count = self.env['maintenance.request'].search_count([('vessel_id', '=', job.vessel_id.id)]) if job.vessel_id else 0

    def action_open_maintenance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vessel Maintenance',
            'res_model': 'maintenance.request',
            'view_mode': 'kanban,tree,form,calendar',
            'domain': [('vessel_id', '=', self.vessel_id.id)],
        }


class SedarDashboard(models.Model):
    _inherit = 'sedar.dashboard'

    open_maintenance = fields.Integer(compute='_compute_maintenance_kpis')
    blocked_vessels = fields.Integer(compute='_compute_maintenance_kpis')
    maintenance_waiting_parts = fields.Integer(compute='_compute_maintenance_kpis')
    maintenance_rfq_count = fields.Integer(compute='_compute_maintenance_kpis')

    def _compute_maintenance_kpis(self):
        waiting = self.env.ref('sedar_operations_integration.maintenance_stage_waiting_parts')
        for dashboard in self:
            open_requests = self.env['maintenance.request'].search([('done', '=', False), ('archive', '=', False)])
            dashboard.open_maintenance = len(open_requests)
            dashboard.blocked_vessels = len(set(open_requests.filtered(lambda item: item.blocks_operation).mapped('vessel_id').ids))
            dashboard.maintenance_waiting_parts = len(open_requests.filtered(lambda item: item.stage_id == waiting))
            dashboard.maintenance_rfq_count = self.env['purchase.order'].search_count([
                ('sedar_maintenance_request_id', '!=', False),
                ('state', 'in', ('draft', 'sent')),
            ])

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SedarVessel(models.Model):
    _inherit = 'sedar.vessel'

    stock_location_id = fields.Many2one('stock.location', copy=False, check_company=True)

    def _sedar_get_stock_location(self):
        self.ensure_one()
        if self.stock_location_id:
            return self.stock_location_id
        parent = self.env.ref('stock.stock_location_locations')
        location = self.env['stock.location'].create({
            'name': 'Vessel - %s' % self.name,
            'location_id': parent.id,
            'usage': 'internal',
            'company_id': self.env.company.id,
        })
        self.stock_location_id = location
        return location


class SedarStockIssue(models.Model):
    _name = 'sedar.stock.issue'
    _description = 'Vessel Stock Issue and Consumption'
    _order = 'movement_date desc, id desc'

    name = fields.Char(default='New', readonly=True, copy=False, required=True)
    movement_date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    movement_type = fields.Selection(
        [('issue', 'Issue to Vessel'), ('consume', 'Consume on Vessel')],
        default='issue',
        required=True,
    )
    vessel_id = fields.Many2one('sedar.vessel', required=True, index=True)
    source_location_id = fields.Many2one('stock.location', domain=[('usage', '=', 'internal')], check_company=True)
    maintenance_request_id = fields.Many2one('maintenance.request', index=True)
    job_order_id = fields.Many2one('sedar.job.order', index=True)
    fuel_log_id = fields.Many2one('sedar.fuel.log', index=True)
    responsible_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    purpose = fields.Text(required=True)
    line_ids = fields.One2many('sedar.stock.issue.line', 'issue_id', copy=True)
    picking_id = fields.Many2one('stock.picking', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('ready', 'Ready'), ('done', 'Done'), ('cancelled', 'Cancelled')],
        default='draft',
        required=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('name', 'New') == 'New':
                values['name'] = self.env['ir.sequence'].next_by_code('sedar.stock.issue') or 'New'
        return super().create(values_list)

    @api.onchange('maintenance_request_id')
    def _onchange_maintenance_request_id(self):
        if self.maintenance_request_id:
            self.vessel_id = self.maintenance_request_id.vessel_id

    @api.onchange('job_order_id')
    def _onchange_job_order_id(self):
        if self.job_order_id:
            self.vessel_id = self.job_order_id.vessel_id

    def _get_locations(self):
        self.ensure_one()
        vessel_location = self.vessel_id._sedar_get_stock_location()
        if self.movement_type == 'issue':
            if not self.source_location_id:
                raise UserError('Select the warehouse source location before issuing stock to a vessel.')
            return self.source_location_id, vessel_location
        consumption_location = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not consumption_location:
            consumption_location = self.env['stock.location'].create({
                'name': 'Vessel Consumption',
                'location_id': self.env.ref('stock.stock_location_locations').id,
                'usage': 'production',
                'company_id': self.company_id.id,
            })
        return vessel_location, consumption_location

    def action_prepare(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Only draft vessel stock movements can be prepared.')
        if not self.line_ids:
            raise UserError('Add at least one product before preparing the stock movement.')
        source, destination = self._get_locations()
        for line in self.line_ids:
            available = line.product_id.with_context(location=source.id).qty_available
            if float_compare(
                line.quantity,
                available,
                precision_rounding=line.product_uom_id.rounding,
            ) > 0:
                raise UserError(
                    'Not enough %s in %s. Required: %s; available: %s.'
                    % (line.product_id.display_name, source.display_name, line.quantity, available)
                )
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not picking_type:
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
            if not warehouse:
                raise UserError('Configure a warehouse before preparing vessel stock movements.')
            picking_type = self.env['stock.picking.type'].create({
                'name': 'Internal Transfers',
                'sequence_code': 'INT',
                'code': 'internal',
                'company_id': self.company_id.id,
                'warehouse_id': warehouse.id,
                'default_location_src_id': warehouse.lot_stock_id.id,
                'default_location_dest_id': warehouse.lot_stock_id.id,
            })
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'origin': self.name,
            'sedar_stock_issue_id': self.id,
            'sedar_maintenance_request_id': self.maintenance_request_id.id,
            'move_ids_without_package': [
                (0, 0, {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom_id.id,
                    'location_id': source.id,
                    'location_dest_id': destination.id,
                })
                for line in self.line_ids
            ],
        })
        picking.action_confirm()
        picking.action_assign()
        self.write({'picking_id': picking.id, 'state': 'ready'})
        return picking

    def action_validate(self):
        for issue in self:
            if issue.state != 'ready' or not issue.picking_id:
                raise UserError('Prepare the vessel stock movement before validating it.')
            if issue.picking_id.state == 'done':
                issue.state = 'done'
                continue
            issue.picking_id.move_ids.write({'picked': True})
            result = issue.picking_id.button_validate()
            if isinstance(result, dict):
                raise UserError('The stock transfer needs manual quantity or backorder review.')
            issue.state = 'done'
        return True

    def action_cancel(self):
        for issue in self:
            if issue.state == 'done':
                raise UserError('A completed stock movement must be reversed with a return transfer.')
            if issue.picking_id and issue.picking_id.state != 'cancel':
                issue.picking_id.action_cancel()
            issue.state = 'cancelled'
        return True


class SedarStockIssueLine(models.Model):
    _name = 'sedar.stock.issue.line'
    _description = 'Vessel Stock Movement Line'
    _order = 'issue_id, id'

    issue_id = fields.Many2one('sedar.stock.issue', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float(default=1.0, required=True)
    product_uom_id = fields.Many2one('uom.uom', required=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.constrains('quantity')
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError('Stock movement quantity must be greater than zero.')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sedar_stock_issue_id = fields.Many2one('sedar.stock.issue', copy=False, index=True)


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    stock_issue_ids = fields.One2many('sedar.stock.issue', 'maintenance_request_id')

    def action_create_part_consumption(self):
        self.ensure_one()
        if not self.vessel_id:
            raise UserError('Link the maintenance equipment to a vessel before consuming parts.')
        if not self.part_line_ids:
            raise UserError('Add required parts before creating vessel consumption.')
        existing = self.stock_issue_ids.filtered(lambda issue: issue.state != 'cancelled')[:1]
        if existing:
            return existing
        return self.env['sedar.stock.issue'].create({
            'movement_type': 'consume',
            'vessel_id': self.vessel_id.id,
            'maintenance_request_id': self.id,
            'purpose': 'Parts consumed for %s' % self.name,
            'line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.required_qty,
                    'product_uom_id': line.product_uom_id.id,
                })
                for line in self.part_line_ids
            ],
        })


class SedarFuelLog(models.Model):
    _inherit = 'sedar.fuel.log'

    product_id = fields.Many2one('product.product', domain=[('type', '!=', 'service')])
    stock_issue_id = fields.Many2one('sedar.stock.issue', readonly=True, copy=False)

    def action_create_stock_consumption(self):
        self.ensure_one()
        if self.stock_issue_id:
            return self.stock_issue_id
        if not self.product_id:
            raise UserError('Select the fuel inventory product before creating stock consumption.')
        issue = self.env['sedar.stock.issue'].create({
            'movement_type': 'consume',
            'vessel_id': self.vessel_id.id,
            'job_order_id': self.job_order_id.id,
            'fuel_log_id': self.id,
            'purpose': 'Fuel consumed on %s' % self.date,
            'line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'quantity': self.liters,
                'product_uom_id': self.product_id.uom_id.id,
            })],
        })
        self.stock_issue_id = issue
        return issue

import base64
from html import escape
from pathlib import Path

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sedar_item_size = fields.Char(string="Size / Specification")
    sedar_tug_use = fields.Selection(
        [("all", "Free-for-all Tugboats"), ("specific", "Specific Tugboat Only")],
        string="Tugboat Use",
        default="all",
        tracking=True,
    )
    sedar_vessel_id = fields.Many2one("sedar.vessel", string="Specific Tugboat")
    sedar_critical_part = fields.Boolean(string="Critical Tugboat Part")


class ResPartner(models.Model):
    _inherit = "res.partner"

    sedar_supplier_accreditation = fields.Selection(
        [
            ("none", "Not Accredited"),
            ("pending", "Pending Management Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Supplier Accreditation",
        default="none",
        tracking=True,
    )
    sedar_discount_notes = fields.Text(string="Discount Notes")
    sedar_reliability_notes = fields.Text(string="Reliability / Relationship Notes")


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def action_sedar_apply_company_profile(self):
        country = self.env.ref("base.ph", raise_if_not_found=False)
        logo_path = Path(__file__).resolve().parents[2] / "sedar_theme/static/src/img/sedar-logo-wide.png"
        values = {
            "name": "Sedar Tug Services Corp.",
            "street": "G/F LS Bldg., Rizal Avenue Ext., Brgy. Sta Clara",
            "street2": False,
            "city": "Batangas City",
            "state_id": False,
            "zip": False,
            "phone": "(043) 722-1263 / Telefax: (043) 786-1354",
            "email": "sedar@sedartug.com",
            "website": "https://www.sedartug.com/",
            "report_footer": "(043) 722-1263 / Telefax: (043) 786-1354 | sedar@sedartug.com | https://www.sedartug.com/",
        }
        if country:
            values["country_id"] = country.id
        if logo_path.exists():
            values["logo"] = base64.b64encode(logo_path.read_bytes())
        self.env.company.write(values)
        self.env.company.partner_id.write(
            {key: value for key, value in values.items() if key in self.env.company.partner_id._fields}
        )
        return True


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _sedar_php_currency(self):
        return self.env.ref("base.PHP", raise_if_not_found=False)

    def _default_currency_id(self):
        return self._sedar_php_currency() or super()._default_currency_id()

    sedar_budget_amount = fields.Monetary(string="Budget Amount")
    sedar_over_budget = fields.Boolean(string="Over Budget", compute="_compute_sedar_over_budget", store=True)
    sedar_canvassing_required = fields.Boolean(
        string="Canvassing Required", compute="_compute_sedar_over_budget", store=True
    )
    sedar_canvassing_done = fields.Boolean(string="Canvassing Done")
    sedar_urgent_exception = fields.Boolean(string="Urgent Single-Supplier Exception")
    sedar_exception_reason = fields.Text(string="Exception Reason")
    sedar_maintenance_id = fields.Many2one("sedar.maintenance.work.order", string="Related Maintenance")
    sedar_inventory_product_id = fields.Many2one("product.product", string="Main Inventory Item")
    sedar_vessel_id = fields.Many2one("sedar.vessel", string="Supplied Tugboat")
    sedar_quote_ids = fields.One2many("sedar.supplier.quote", "purchase_id", string="Canvas Sheet Quotes")
    sedar_quote_count = fields.Integer(compute="_compute_sedar_quote_count")
    sedar_canvas_summary_html = fields.Html(
        string="Quote Comparison Summary", compute="_compute_sedar_canvas_summary_html", sanitize=False
    )
    sedar_budget_amount_display = fields.Char(string="Budget Amount", compute="_compute_sedar_amount_displays")
    sedar_amount_total_display = fields.Char(string="Total", compute="_compute_sedar_amount_displays")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        php = self._sedar_php_currency()
        if php and "currency_id" in fields_list:
            values["currency_id"] = php.id
        return values

    @api.model_create_multi
    def create(self, vals_list):
        php = self._sedar_php_currency()
        if php:
            php.active = True
            for values in vals_list:
                values["currency_id"] = php.id
        return super().create(vals_list)

    def _sedar_format_php(self, amount):
        return f"PHP {amount or 0.0:,.2f}"

    @api.depends("sedar_budget_amount", "amount_total")
    def _compute_sedar_amount_displays(self):
        for order in self:
            order.sedar_budget_amount_display = order._sedar_format_php(order.sedar_budget_amount)
            order.sedar_amount_total_display = order._sedar_format_php(order.amount_total)

    @api.depends("amount_total", "sedar_budget_amount", "sedar_urgent_exception")
    def _compute_sedar_over_budget(self):
        for order in self:
            over_budget = bool(order.sedar_budget_amount and order.amount_total > order.sedar_budget_amount)
            order.sedar_over_budget = over_budget
            order.sedar_canvassing_required = over_budget and not order.sedar_urgent_exception

    @api.depends("sedar_quote_ids")
    def _compute_sedar_quote_count(self):
        for order in self:
            order.sedar_quote_count = len(order.sedar_quote_ids)

    @api.depends(
        "order_line.product_id",
        "order_line.name",
        "order_line.product_qty",
        "sedar_quote_ids.partner_id",
        "sedar_quote_ids.product_id",
        "sedar_quote_ids.price_total",
        "sedar_quote_ids.lead_time_days",
        "sedar_quote_ids.discount_notes",
        "sedar_quote_ids.reliability_notes",
        "sedar_quote_ids.selected",
        "currency_id",
        "amount_total",
        "sedar_budget_amount",
    )
    def _compute_sedar_canvas_summary_html(self):
        for order in self:
            order.sedar_canvas_summary_html = order._get_sedar_canvas_summary_html()

    def _get_sedar_canvas_summary_html(self):
        self.ensure_one()
        quotes = self.sedar_quote_ids.sorted(lambda quote: (quote.price_total, quote.quote_received_at or fields.Datetime.now()))
        lowest_quote = quotes[:1]
        selected_quote = quotes.filtered("selected")[:1]
        budget_gap = self.sedar_budget_amount - self.amount_total if self.sedar_budget_amount else 0

        def money(amount):
            return self._sedar_format_php(amount)

        lines = self.order_line.filtered(lambda line: not line.display_type)
        first_line = lines[:1]
        first_quote_product = quotes.filtered("product_id")[:1].product_id
        item_name = first_line.product_id.display_name or first_line.name or first_quote_product.display_name or "No item selected"
        item_qty = f"Qty {first_line.product_qty:g}" if first_line else "Add items on the PO/RFQ lines"

        supplier_cards = []
        seen_suppliers = set()
        for quote in quotes:
            if quote.partner_id.id in seen_suppliers:
                continue
            seen_suppliers.add(quote.partner_id.id)
            supplier_cards.append(quote)
            if len(supplier_cards) == 3:
                break

        html = ["<div class='sedar_canvas_summary'>"]
        html.append("<div class='sedar_canvas_brief'>")
        html.append(f"<section><span>Item</span><strong>{escape(item_name)}</strong><small>{escape(item_qty)}</small></section>")
        html.append(f"<section><span>Budget</span><strong>{money(self.sedar_budget_amount)}</strong><small>Total {money(self.amount_total)}</small></section>")
        html.append(
            f"<section><span>Best Quote</span><strong>{money(lowest_quote.price_total) if lowest_quote else 'No quotes yet'}</strong>"
            f"<small>{escape(lowest_quote.partner_id.display_name) if lowest_quote else 'Add supplier quotes below'}</small></section>"
        )
        html.append(
            f"<section><span>Selected</span><strong>{escape(selected_quote.partner_id.display_name) if selected_quote else 'Not selected'}</strong>"
            f"<small>Budget gap {money(budget_gap)}</small></section>"
        )
        html.append("</div>")

        html.append("<div class='sedar_canvas_supplier_cards'>")
        for index in range(3):
            quote = supplier_cards[index] if index < len(supplier_cards) else self.env["sedar.supplier.quote"]
            if quote:
                selected = '<span class="sedar_canvas_badge">Selected</span>' if quote.selected else ""
                lowest = '<span class="sedar_canvas_lowest">Lowest</span>' if lowest_quote and quote == lowest_quote else ""
                quote_item = quote.product_id.display_name or item_name
                lead = f"{quote.lead_time_days} days" if quote.lead_time_days else "Not stated"
                discount = escape(quote.discount_notes or "No discount noted")
                reliability = escape(quote.reliability_notes or "No reliability note")
                html.append(
                    "<section class='sedar_canvas_supplier_card'>"
                    f"<div><span>Supplier {index + 1}</span>{selected}{lowest}</div>"
                    f"<h3>{escape(quote.partner_id.display_name)}</h3>"
                    f"<strong>{money(quote.price_total)}</strong>"
                    f"<dl><dt>Item</dt><dd>{escape(quote_item)}</dd>"
                    f"<dt>Lead Time</dt><dd>{escape(lead)}</dd>"
                    f"<dt>Discount / Terms</dt><dd>{discount}</dd>"
                    f"<dt>Reliability</dt><dd>{reliability}</dd></dl>"
                    "</section>"
                )
            else:
                html.append(
                    "<section class='sedar_canvas_supplier_card is-empty'>"
                    f"<div><span>Supplier {index + 1}</span></div>"
                    "<h3>No quote yet</h3><strong>--</strong>"
                    "<p>Add this supplier quote in the entry table below.</p>"
                    "</section>"
                )
        html.append("</div>")
        html.append("</div>")
        return "".join(html)

    def button_confirm(self):
        for order in self:
            if order.sedar_canvassing_required and not order.sedar_canvassing_done:
                raise UserError(_("This PO is over budget. Complete canvassing or mark an urgent exception first."))
            if order.sedar_urgent_exception and not order.sedar_exception_reason:
                raise UserError(_("Add the urgent exception reason before confirming this PO."))
        return super().button_confirm()

    def action_sedar_print_canvas(self):
        self.ensure_one()
        return self.env.ref("sedar_procurement.action_report_sedar_canvas_sheet").report_action(self)

    def action_sedar_save_draft(self):
        return self.env.ref("sedar_procurement.action_sedar_procurement_dashboard").read()[0]

    def action_sedar_confirm_po(self):
        self.button_confirm()
        return self.env.ref("sedar_procurement.action_sedar_procurement_dashboard").read()[0]

    @api.model
    def action_sedar_get_flow_form_view_id(self):
        return self.env.ref("sedar_procurement.view_sedar_purchase_flow_form").id

    @api.model
    def action_sedar_use_php_currency(self):
        php = self.env.ref("base.PHP", raise_if_not_found=False)
        if not php:
            return True
        php.active = True
        self.search([]).write({"currency_id": php.id})
        return True


class SedarSupplierQuote(models.Model):
    _name = "sedar.supplier.quote"
    _description = "SEDAR Supplier Quote"
    _order = "quote_received_at, price_total"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    purchase_id = fields.Many2one("purchase.order", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Supplier", required=True, tracking=True)
    product_id = fields.Many2one("product.product", string="Item")
    quote_received_at = fields.Datetime(string="Quote Received", tracking=True)
    price_total = fields.Monetary(string="Quoted Price", tracking=True)
    currency_id = fields.Many2one(related="purchase_id.currency_id", store=True, readonly=True)
    lead_time_days = fields.Integer(string="Lead Time Days")
    discount_notes = fields.Text(string="Discount Offered")
    reliability_notes = fields.Text(string="Reliability Notes")
    selected = fields.Boolean(string="Selected Supplier", tracking=True)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sedar_price_unit_display = fields.Char(string="Unit Price", compute="_compute_sedar_price_displays")
    sedar_price_subtotal_display = fields.Char(string="Subtotal", compute="_compute_sedar_price_displays")

    @api.depends("price_unit", "price_subtotal")
    def _compute_sedar_price_displays(self):
        for line in self:
            line.sedar_price_unit_display = f"PHP {line.price_unit or 0.0:,.2f}"
            line.sedar_price_subtotal_display = f"PHP {line.price_subtotal or 0.0:,.2f}"


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sedar_vessel_id = fields.Many2one("sedar.vessel", string="Issued To Tugboat", tracking=True)
    sedar_issue_reason = fields.Char(string="Issue Reason")

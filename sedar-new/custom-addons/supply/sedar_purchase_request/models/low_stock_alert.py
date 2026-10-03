from odoo import _, models


LOW_STOCK_ACTIVITY_TYPE = "sedar_purchase_request.mail_activity_type_low_stock"


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, *args, **kwargs):
        moves = super()._action_done(*args, **kwargs)
        for company in moves.company_id:
            products = moves.filtered(lambda move: move.company_id == company).product_id
            products.with_company(company)._sync_low_stock_alert()
        return moves


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _sync_low_stock_alert(self):
        officer = self.env.company.sedar_procurement_inventory_officer_id
        items = self.filtered("sedar_inventory_item")
        if not officer.active or not items:
            return
        activity_type = self.env.ref(LOW_STOCK_ACTIVITY_TYPE)
        items.invalidate_recordset(["sedar_stock_status"])
        for product in items.sudo():
            open_alerts = product.env["mail.activity"].search([
                ("res_model", "=", product._name), ("res_id", "=", product.id),
                ("activity_type_id", "=", activity_type.id), ("user_id", "=", officer.id),
            ])
            status = product.sedar_stock_status
            if status != "in_stock":
                if not open_alerts:
                    product.activity_schedule(
                        LOW_STOCK_ACTIVITY_TYPE,
                        user_id=officer.id,
                        summary=(
                            _("Out of stock: %s", product.display_name)
                            if status == "out_of_stock"
                            else _("Low stock: %s", product.display_name)
                        ),
                        note=_(
                            "%(available)s available to issue; Reorder Point is %(reorder)s. "
                            "Raise a Purchase Request if this item needs buying.",
                            available=product.sedar_available_to_issue,
                            reorder=product.sedar_reorder_point,
                        ),
                    )
            elif open_alerts:
                open_alerts.action_feedback(feedback=_("Stock is back above the Reorder Point."))

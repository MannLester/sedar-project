from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _sedar_set_book_currency(self, currency_id):
        self.env.cr.execute(
            "UPDATE res_company SET currency_id = %s WHERE id IN %s",
            [currency_id, tuple(self.ids)],
        )
        self.invalidate_recordset(["currency_id"])


class AccountMove(models.Model):
    _inherit = "account.move"

    sedar_purchase_id = fields.Many2one("purchase.order", string="Finance Purchase Order", copy=False, index=True, check_company=True)
    sedar_maintenance_request_id = fields.Many2one(
        "maintenance.request", string="Maintenance Work Order", copy=False, index=True,
    )
    sedar_petty_cash_id = fields.Many2one("sedar.finance.petty.cash", string="Petty Cash", copy=False, index=True, check_company=True)
    sedar_cash_advance_id = fields.Many2one("sedar.finance.cash.advance", string="Cash Advance", copy=False, index=True, check_company=True)
    sedar_advance_liquidation_id = fields.Many2one(
        "sedar.finance.advance.liquidation", string="Advance Liquidation", copy=False, index=True, check_company=True,
    )
    sedar_disbursement_id = fields.Many2one("sedar.finance.disbursement", copy=False, index=True, check_company=True)
    sedar_collection_id = fields.Many2one("sedar.finance.collection", copy=False, index=True, check_company=True)
    sedar_finance_billing_id = fields.Many2one("sedar.towage.billing", string="Finance Billing", copy=False, index=True)
    sedar_bank_adjustment_id = fields.Many2one("sedar.finance.bank.adjustment", copy=False, index=True, check_company=True)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    sedar_purchase_id = fields.Many2one(related="move_id.sedar_purchase_id", string="Finance Purchase Order", store=True, index=True)
    sedar_vessel_id = fields.Many2one(related="move_id.sedar_vessel_id", store=True, index=True)
    sedar_job_order_id = fields.Many2one(related="move_id.sedar_job_order_id", store=True, index=True)
    sedar_maintenance_request_id = fields.Many2one(
        related="move_id.sedar_maintenance_request_id", string="Maintenance Work Order", store=True, index=True,
    )
    sedar_petty_cash_id = fields.Many2one(related="move_id.sedar_petty_cash_id", store=True, index=True)
    sedar_cash_advance_id = fields.Many2one(related="move_id.sedar_cash_advance_id", store=True, index=True)
    sedar_advance_liquidation_id = fields.Many2one(related="move_id.sedar_advance_liquidation_id", store=True, index=True)
    sedar_disbursement_id = fields.Many2one(related="move_id.sedar_disbursement_id", store=True, index=True)
    sedar_collection_id = fields.Many2one(related="move_id.sedar_collection_id", store=True, index=True)
    sedar_finance_billing_id = fields.Many2one(related="move_id.sedar_finance_billing_id", store=True, index=True)
    sedar_bank_adjustment_id = fields.Many2one(related="move_id.sedar_bank_adjustment_id", store=True, index=True)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    sedar_disbursement_id = fields.Many2one("sedar.finance.disbursement", copy=False, index=True, check_company=True)
    sedar_collection_id = fields.Many2one("sedar.finance.collection", copy=False, index=True, check_company=True)
    sedar_collection_invoice_id = fields.Many2one("account.move", string="Collected Invoice", copy=False, index=True, check_company=True)
    sedar_purchase_id = fields.Many2one("purchase.order", string="Finance Purchase Order", copy=False, index=True, check_company=True)
    sedar_vessel_id = fields.Many2one("sedar.vessel", copy=False, index=True)
    sedar_job_order_id = fields.Many2one("sedar.job.order", string="Job", copy=False, index=True)
    sedar_maintenance_request_id = fields.Many2one(
        "maintenance.request", string="Maintenance Work Order", copy=False, index=True,
    )
    sedar_check_number = fields.Char(string="Finance Check Reference", copy=False, index=True)
    sedar_bank_reference = fields.Char(string="Bank Reference", copy=False, index=True)

    def _synchronize_to_moves(self, changed_fields):
        result = super()._synchronize_to_moves(changed_fields)
        for payment in self:
            payment.move_id.write({
                "sedar_purchase_id": payment.sedar_purchase_id.id,
                "sedar_vessel_id": payment.sedar_vessel_id.id,
                "sedar_job_order_id": payment.sedar_job_order_id.id,
                "sedar_maintenance_request_id": payment.sedar_maintenance_request_id.id,
                "sedar_disbursement_id": payment.sedar_disbursement_id.id,
                "sedar_collection_id": payment.sedar_collection_id.id,
            })
        return result

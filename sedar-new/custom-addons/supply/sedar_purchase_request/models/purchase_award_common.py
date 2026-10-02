from datetime import datetime, time
import pytz
from odoo import fields


AWARD_INTERNAL_CONTEXT = "sedar_award_workflow"


AWARD_MUTABLE_FIELDS = {"active_request_line_id", "state", "reset_reason", "reset_by_id", "reset_at", "purchase_order_line_id"}


PO_LINE_SOURCE_FIELDS = {
    "sedar_purchase_request_line_id", "sedar_bid_line_id", "sedar_line_award_id",
}


GENERATED_ORDER_FACT_FIELDS = {"partner_id", "company_id", "currency_id"}


GENERATED_LINE_FACT_FIELDS = {
    "order_id", "product_id", "product_uom_id", "product_qty", "price_unit",
    "discount", "technical_price_unit",
}


RECOVERY_AUDIT_FIELDS = {
    "handoff_recovery_reason", "handoff_recovered_by_id", "handoff_recovered_at",
}


def _company_business_date(record):
    company = record.company_id
    timezone = company.partner_id.tz or company.sedar_procurement_inventory_officer_id.tz or "UTC"
    return fields.Date.context_today(record.with_context(tz=timezone))


def _company_midnight_utc(company, date_value):
    timezone = company.partner_id.tz or company.sedar_procurement_inventory_officer_id.tz or "UTC"
    localized = pytz.timezone(timezone).localize(datetime.combine(date_value, time.min))
    return localized.astimezone(pytz.UTC).replace(tzinfo=None)

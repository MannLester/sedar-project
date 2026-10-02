from odoo.exceptions import ValidationError


BID_AUDIT_FIELDS = {
    "state",
    "capture_source",
    "received_by_id",
    "received_at",
    "withdrawn_by_id",
    "withdrawn_at",
}


BID_COMMERCIAL_FIELDS = {
    "request_id",
    "bidder_id",
    "received_date",
    "validity_date",
    "promised_delivery_date",
    "delivery_terms",
    "availability_notes",
    "payment_terms",
    "warranty_notes",
    "commercial_notes",
    "quotation_file",
    "quotation_filename",
    "line_ids",
}


def _check_duplicate_value_pairs(
    model, vals_list, first_field, second_field, error_message
):
    seen = set()
    for vals in vals_list:
        key = (vals.get(first_field), vals.get(second_field))
        if not all(key):
            continue
        duplicate = key in seen or model.sudo().search_count([
            (first_field, "=", key[0]),
            (second_field, "=", key[1]),
        ])
        if duplicate:
            raise ValidationError(error_message)
        seen.add(key)

from odoo import Command, SUPERUSER_ID, api, fields


def _is_unambiguous_legacy_request(request):
    bidder = request.vendor_id.commercial_partner_id
    if (
        request.state != "approved"
        or not request.vendor_id
        or request.purchase_order_id
        or request.purchase_order_ids
        or not request.approved_by_id
        or not request.approved_at
        or not request.line_ids
        or not bidder
        or bidder.supplier_rank <= 0
        or (bidder.company_id and bidder.company_id != request.company_id)
    ):
        return False
    return all(
        line.quantity > 0
        and line.estimated_unit_price >= 0
        and line.product_id.type == "consu"
        and (not line.product_id.company_id or line.product_id.company_id == request.company_id)
        for line in request.line_ids
    )


def migrate(cr, version):
    """Convert only approved, vendor-specific legacy requests with complete audit facts."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Bid = env["sedar.purchase.bid"]
    requests = env["sedar.purchase.request"].search([
        ("state", "=", "approved"),
        ("vendor_id", "!=", False),
        ("purchase_order_id", "=", False),
        ("purchase_order_ids", "=", False),
    ])
    for request in requests:
        if request.bid_ids or not _is_unambiguous_legacy_request(request):
            continue
        bidder = request.vendor_id.commercial_partner_id
        values = {
            "request_id": request.id,
            "bidder_id": bidder.id,
            "capture_source": "legacy",
            "state": "received",
            "received_date": fields.Date.to_date(request.approved_at),
            "received_by_id": request.approved_by_id.id,
            "received_at": request.approved_at,
            "line_ids": [
                Command.create({
                    "request_line_id": line.id,
                    "quantity": line.quantity,
                    "unit_price": line.estimated_unit_price,
                })
                for line in request.line_ids
            ],
        }
        Bid.create(values)

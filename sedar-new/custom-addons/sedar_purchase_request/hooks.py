from datetime import datetime

from odoo import Command


MODULE = "sedar_purchase_request"


def _record(env, model, xmlid, values, update=True):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid)
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            if update:
                record.write(values)
            return record
        data.unlink()
    record = env[model].create(values)
    env["ir.model.data"].create({
        "module": MODULE,
        "name": xmlid,
        "model": model,
        "res_id": record.id,
        "noupdate": True,
    })
    return record


def post_init_hook(env):
    company = env.company
    supplier = _record(env, "res.partner", "vendor_marine_supplies", {
        "name": "Demo Marine Supplies Corporation",
        "is_company": True,
        "supplier_rank": 1,
        "email": "procurement@marine-supplies.example.com",
        "phone": "+63 2 8800 2100",
        "country_id": env.ref("base.ph").id,
    })

    manager = _record(env, "res.users", "user_procurement_manager", {
        "name": "Demo Procurement Manager",
        "login": "procurement@sedar.demo",
        "password": "procdemo",
        "company_id": company.id,
        "company_ids": [Command.set([company.id])],
        "group_ids": [Command.set([
            env.ref("base.group_user").id,
            env.ref("sedar_purchase_request.group_sedar_purchase_request_manager").id,
        ])],
    }, update=False)

    part_line = env.ref("sedar_marine_inventory.line_demo_filter_shortage", raise_if_not_found=False)
    product = part_line.product_id if part_line else env.ref(
        "sedar_marine_inventory.product_fuel_filter", raise_if_not_found=False
    )
    location = part_line.source_location_id if part_line else env["stock.warehouse"].search(
        [("company_id", "=", company.id)], limit=1
    ).lot_stock_id
    if not product or not location:
        return

    request = _record(env, "sedar.purchase.request", "request_demo_spare_parts", {
        "requester_id": manager.id,
        "vendor_id": supplier.id,
        "source_type": "maintenance",
        "maintenance_request_id": part_line.maintenance_request_id.id if part_line else False,
        "required_date": datetime(2026, 8, 18, 8, 0, 0),
        "priority": "urgent",
        "justification": "Demo replenishment for maintenance spare-part shortage.",
        "state": "draft",
    }, update=False)

    if not request.line_ids:
        _record(env, "sedar.purchase.request.line", "request_demo_spare_parts_filter", {
            "request_id": request.id,
            "product_id": product.id,
            "quantity": max(part_line.shortage_qty or part_line.requested_qty, 1.0) if part_line else 4.0,
            "estimated_unit_price": 850.0,
            "source_location_id": location.id,
            "maintenance_part_line_id": part_line.id if part_line else False,
            "need_reason": "Demo maintenance part shortage replenishment.",
        }, update=False)

    if request.state == "draft":
        request.action_submit()

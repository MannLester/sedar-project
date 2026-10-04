"""Final, repeatable reconciliation for the complete fictional demonstration."""

import base64
from datetime import date, datetime, timedelta

from odoo import Command
from odoo.exceptions import UserError


UNBOUNDED_BID_VALIDITY = False

DEMO_MANAGER_GROUP_XMLIDS = (
    "sedar_ais_demo.group_sedar_ais_manager",
    "sedar_crew_compliance.group_crew_compliance_manager",
    "sedar_executive_dashboard.group_sedar_executive",
    "sedar_hsse.group_sedar_hsse_manager",
    "sedar_manpower_planning.group_hr_manager",
    "sedar_marine_dispatch.group_dispatch_manager",
    "sedar_marine_finance.group_accounting_manager",
    "sedar_marine_inventory.group_marine_inventory_manager",
    "sedar_marine_maintenance.group_marine_maintenance_manager",
    "sedar_marine_operations.group_commercial_manager",
    "sedar_marine_operations.group_operations_manager",
    "sedar_marketing.group_marketing_manager",
    "sedar_recruitment_crewing.group_crewing_manager",
)


def post_init_hook(env):
    company = env.company
    company.sedar_configure_demo_currency()
    _ensure_accounting_foundation(env, company)
    company.sedar_ensure_erp_demo()
    company.sedar_ensure_recruitment_demo()
    company.sedar_ensure_crew_onboarding_demo()
    company.sedar_ensure_executive_demo()

    from odoo.addons.sedar_service_order_demo.hooks import post_init_hook as reconcile_orders
    from odoo.addons.sedar_marine_dispatch_demo.hooks import post_init_hook as reconcile_dispatch
    from odoo.addons.sedar_marine_inventory.hooks import post_init_hook as reconcile_inventory
    from odoo.addons.sedar_marine_maintenance.hooks import post_init_hook as reconcile_maintenance
    from odoo.addons.sedar_purchase_request.hooks import post_init_hook as reconcile_purchase
    from odoo.addons.sedar_marketing.hooks import post_init_hook as reconcile_marketing
    from odoo.addons.sedar_ais_demo.hooks import post_init_hook as reconcile_ais

    for reconciler in (reconcile_orders, reconcile_dispatch, reconcile_inventory, reconcile_maintenance, reconcile_purchase):
        reconciler(env)

    company.sedar_ensure_erp_demo()
    company._sedar_ensure_accounting_demo(company)
    _ensure_paid_service_demo(env)
    _ensure_finance_scenarios(env)
    _ensure_pm_procurement_demo(env)
    reconcile_marketing(env)
    reconcile_ais(env)
    _ensure_broader_demo_data(env)
    _ensure_inventory_lifecycle_demo(env)
    _ensure_inventory_shortage_demo(env)
    company.sedar_ensure_executive_demo()
    _ensure_demo_internal_access(env)
    return True


def _fixture_data(env, xmlid):
    data = env["ir.model.data"].search([
        ("module", "=", "sedar_demo_suite"),
        ("name", "=", xmlid),
    ])
    if len(data) > 1:
        raise UserError(f"Duplicate fixture identity sedar_demo_suite.{xmlid}.")
    return data


def _record(env, model, xmlid, values, update=True):
    data = _fixture_data(env, xmlid)
    if data:
        if data.model != model:
            raise UserError(
                f"Fixture sedar_demo_suite.{xmlid} points to {data.model}, "
                f"not {model}; reconciliation stopped without changing it."
            )
        record = env[model].browse(data.res_id).exists()
        if record:
            if update:
                record.write(values)
            return record
        data.unlink()
    record = env[model].create(values)
    env["ir.model.data"].create({
        "module": "sedar_demo_suite",
        "name": xmlid,
        "model": model,
        "res_id": record.id,
        "noupdate": True,
    })
    return record


def _identity_value(record, field_name):
    value = record[field_name]
    return value.id if record._fields[field_name].type == "many2one" else value


def _validate_immutable_identity(
    env, record, xmlid, values, identity_fields
):
    if "company_id" in record._fields and record.company_id != env.company:
        raise UserError(
            f"Fixture sedar_demo_suite.{xmlid} belongs to another company; "
            "reconciliation stopped without changing it."
        )
    mismatched = [
        field_name
        for field_name in identity_fields
        if _identity_value(record, field_name) != values[field_name]
    ]
    if mismatched:
        raise UserError(
            f"Fixture sedar_demo_suite.{xmlid} has mismatched business identity "
            f"({', '.join(mismatched)}); reconciliation stopped without changing it."
        )


def _immutable_record(
    env, model, xmlid, values, *, identity_fields
):
    """Create one immutable fixture or verify its exact stable identity."""
    record = _resolve_immutable_record(
        env, model, xmlid, values, identity_fields=identity_fields
    )
    if record:
        return record
    record = env[model].create(values)
    _validate_immutable_identity(env, record, xmlid, values, identity_fields)
    return _bind_xmlid(env, xmlid, record)


def _resolve_immutable_record(
    env, model, xmlid, values, *, identity_fields
):
    data = _fixture_data(env, xmlid)
    if not data:
        return env[model]
    if data.model != model:
        raise UserError(
            f"Fixture sedar_demo_suite.{xmlid} points to {data.model}, "
            f"not {model}; reconciliation stopped without changing it."
        )
    record = env[model].browse(data.res_id).exists()
    if not record:
        raise UserError(
            f"Fixture sedar_demo_suite.{xmlid} points to a missing record; "
            "reconciliation stopped instead of fabricating history."
        )
    _validate_immutable_identity(env, record, xmlid, values, identity_fields)
    return record


def _bind_xmlid(env, xmlid, record):
    """Give an exact, already-resolved fixture record a stable suite identity."""
    record.ensure_one()
    data = _fixture_data(env, xmlid)
    if data and data.model == record._name and data.res_id == record.id:
        return record
    if data:
        raise UserError(
            f"Fixture sedar_demo_suite.{xmlid} already points to another record; "
            "reconciliation stopped without rebinding it."
        )
    env["ir.model.data"].create({
        "module": "sedar_demo_suite",
        "name": xmlid,
        "model": record._name,
        "res_id": record.id,
        "noupdate": True,
    })
    return record


def _first(env, model, domain=None, order="id"):
    return env[model].search(domain or [], order=order, limit=1)


def _ensure_demo_internal_access(env):
    """Apply the temporary all-workspaces override to internal demo personas."""
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    demo_users = env["res.users"].sudo().search([
        ("active", "=", True),
        ("share", "=", False),
        ("login", "=like", "%@sedar.demo"),
    ])
    users = demo_users | admin if admin else demo_users
    if not users:
        return
    groups = [
        env.ref(xmlid, raise_if_not_found=False)
        for xmlid in DEMO_MANAGER_GROUP_XMLIDS
    ]
    users.write({
        "group_ids": [Command.link(group.id) for group in groups if group],
    })


def _ensure_accounting_foundation(env, company):
    """Load Odoo's generic chart only when a fresh demo company has no ledger setup."""
    journals = env["account.journal"].search_count([
        ("company_id", "=", company.id),
        ("type", "in", ["sale", "purchase", "bank"]),
    ])
    if journals:
        return
    env["account.chart.template"].try_loading(
        "generic_coa", company, install_demo=False
    )
    company.sedar_configure_demo_currency()


def _ensure_paid_service_demo(env):
    """Create one posted and paid invoice through the normal billing flow."""
    billing_user = env.ref("sedar_service_order_demo.user_billing_officer", raise_if_not_found=False)
    if not billing_user:
        return
    order = env.ref("sedar_service_order_demo.order_completed", raise_if_not_found=False)
    if not order:
        return
    order = order.with_user(billing_user)
    if order.billing_status != "review" and not order.invoice_ids:
        return
    if order.billing_status == "review":
        order.action_mark_billing_reviewed()
    if not order.invoice_ids.filtered(lambda move: move.move_type == "out_invoice" and move.state != "cancel"):
        order.action_create_draft_invoice()
    invoice = order.invoice_ids.filtered(lambda move: move.move_type == "out_invoice" and move.state != "cancel")[:1]
    if invoice and invoice.state == "draft":
        invoice.action_post()
    if invoice and invoice.payment_state != "paid":
        register = env["account.payment.register"].with_user(billing_user).with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({})
        register._create_payments()


def _ensure_finance_scenarios(env):
    company = env.company
    journal = _first(env, "account.journal", [
        ("company_id", "=", company.id), ("type", "=", "sale"),
    ])
    product = env.ref("sedar_marine_finance.product_marine_service", raise_if_not_found=False)
    partner = _record(env, "res.partner", "finance_scenario_customer", {
        "name": "Demo Harbor Logistics Corporation",
        "is_company": True,
        "customer_rank": 1,
        "company_id": company.id,
    })
    if not journal or not product:
        return
    today = date.today()
    current_month_offset = -min(max(today.day - 1, 0), 2)
    scenarios = (
        ("finance_invoice_month", "DEMO-FIN-THIS-MONTH", current_month_offset, 20, 105000, True),
        ("finance_invoice_draft", "DEMO-FIN-DRAFT", -2, 14, 58000, False),
        ("finance_invoice_current", "DEMO-FIN-CURRENT", -5, 12, 92000, True),
        ("finance_invoice_overdue_18", "DEMO-FIN-OVERDUE-18", -35, -18, 76000, True),
        ("finance_invoice_overdue_46", "DEMO-FIN-OVERDUE-46", -70, -46, 124000, True),
        ("finance_invoice_partial", "DEMO-FIN-PARTIAL", -28, -12, 88000, True),
        ("finance_invoice_paid", "DEMO-FIN-PAID", -24, -8, 64000, True),
    )
    invoices = {}
    for xmlid, reference, invoice_offset, due_offset, amount, post in scenarios:
        invoice = _record(env, "account.move", xmlid, {
            "move_type": "out_invoice",
            "company_id": company.id,
            "journal_id": journal.id,
            "partner_id": partner.id,
            "invoice_date": today + timedelta(days=invoice_offset),
            "invoice_date_due": today + timedelta(days=due_offset),
            "invoice_origin": f"Finance walkthrough · {reference}",
            "ref": reference,
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "name": "Demo marine tug assistance",
                "quantity": 1,
                "price_unit": amount,
            })],
        }, update=False)
        if post and invoice.state == "draft":
            invoice.action_post()
        invoices[xmlid] = invoice
    _ensure_demo_invoice_payment(env, invoices["finance_invoice_partial"], 36000)
    _ensure_demo_invoice_payment(env, invoices["finance_invoice_paid"], 64000)
    credit = _record(env, "account.move", "finance_credit_note", {
        "move_type": "out_refund",
        "company_id": company.id,
        "journal_id": journal.id,
        "partner_id": partner.id,
        "invoice_date": today - timedelta(days=6),
        "ref": "DEMO-FIN-CREDIT",
        "invoice_origin": "Finance walkthrough · service adjustment",
        "invoice_line_ids": [Command.create({
            "product_id": product.id,
            "name": "Demo service adjustment credit",
            "quantity": 1,
            "price_unit": 12000,
        })],
    }, update=False)
    if credit.state == "draft":
        credit.action_post()


def _ensure_demo_invoice_payment(env, invoice, amount):
    if invoice.state != "posted" or invoice.payment_state in {"paid", "reversed"}:
        return
    already_applied = invoice.amount_total - invoice.amount_residual
    remaining_payment = min(amount - already_applied, invoice.amount_residual)
    if remaining_payment <= 0:
        return
    register = env["account.payment.register"].with_context(
        active_model="account.move", active_ids=invoice.ids,
    ).create({
        "amount": remaining_payment,
        "payment_date": date.today() - timedelta(days=4),
    })
    register._create_payments()


def _ensure_pm_procurement_demo(env):
    """Reconcile the approved three-product procurement walkthrough."""
    officer = env.ref(
        "sedar_purchase_request.user_procurement_manager",
        raise_if_not_found=False,
    )
    equipment = env.ref(
        "sedar_marine_maintenance.atlas_main_engine",
        raise_if_not_found=False,
    )
    work_order = env.ref(
        "sedar_marine_maintenance.work_order_atlas_planned",
        raise_if_not_found=False,
    )
    storage = env.company.sedar_default_storage_location_id
    if not all((officer, equipment, work_order, storage)):
        return

    products = _ensure_pm_products(env)
    bidders = _ensure_pm_bidders(env)
    request, lines = _ensure_pm_request(
        env, officer, equipment, work_order, storage, products
    )
    bids = _ensure_pm_bids(env, officer, request, lines, bidders)
    _ensure_pm_awards(env, officer, lines, bids)
    orders = _ensure_pm_orders(env, officer, request, bids, products)
    _ensure_pm_receipts(env, orders, products)
    _ensure_pm_current_use(
        env, officer, products["a"], equipment.sedar_tugboat_id
    )
    _bind_pm_maintenance_facts(env, equipment)


def _ensure_pm_products(env):
    unit = env.ref("uom.product_uom_unit")
    liter = env.ref("uom.product_uom_litre", raise_if_not_found=False) or unit
    specs = {
        "a": (
            "pm_product_a_filter", "Product A — Main Engine Oil Filter Set",
            "SEDAR-PM-A-FILTER", "ME-OF-500", unit, "spare_part",
        ),
        "b": (
            "pm_product_b_lube", "Product B — Marine Engine Oil",
            "SEDAR-PM-B-LUBE", "MEO-15W40", liter, "fuel_lubricant",
        ),
        "c": (
            "pm_product_c_replacement_pump",
            "Product C — Replacement Cooling-Water Pump",
            "SEDAR-PM-C-PUMP", "CWP-500-R", unit, "replacement_equipment",
        ),
    }
    products = {}
    for key, (xmlid, name, code, part, uom, item_type) in specs.items():
        products[key] = _immutable_record(env, "product.product", xmlid, {
            "name": name,
            "company_id": env.company.id,
            "type": "consu",
            "is_storable": True,
            "uom_id": uom.id,
            "default_code": code,
            "sedar_inventory_item": True,
            "sedar_item_type": item_type,
            "sedar_manufacturer_part_number": part,
            "sedar_compatibility_scope": "fleet",
            "sedar_reorder_point": 0.0,
            "tracking": "serial" if item_type == "replacement_equipment" else "none",
        }, identity_fields=("company_id", "default_code"))
    return products


def _ensure_pm_bidders(env):
    specs = {
        "one": ("pm_bidder_1", "Bidder 1 — Batangas Marine Supply"),
        "two": ("pm_bidder_2", "Bidder 2 — Harbor Parts Trading"),
        "three": ("pm_bidder_3", "Bidder 3 — Pacific Engine Systems"),
    }
    return {
        key: _immutable_record(env, "res.partner", xmlid, {
            "name": name,
            "is_company": True,
            "supplier_rank": 1,
            "company_id": env.company.id,
        }, identity_fields=("company_id", "name"))
        for key, (xmlid, name) in specs.items()
    }


def _ensure_pm_request(
    env, officer, equipment, work_order, storage, products
):
    request = _immutable_record(env, "sedar.purchase.request", "pm_request", {
        "requester_id": officer.id,
        "company_id": env.company.id,
        "currency_id": env.company.currency_id.id,
        "source_type": "maintenance",
        "maintenance_request_id": work_order.id,
        "equipment_id": equipment.id,
        "required_date": datetime(2026, 9, 5, 8, 0, 0),
        "priority": "urgent",
        "justification": (
            "Procure physical maintenance stock for the due STS Atlas main-engine service."
        ),
    }, identity_fields=(
        "company_id", "maintenance_request_id", "equipment_id",
    ))
    line_specs = {
        "a": ("pm_request_line_a", 4.0, 850.0, 10),
        "b": ("pm_request_line_b", 60.0, 320.0, 20),
        "c": ("pm_request_line_c", 1.0, 185000.0, 30),
    }
    lines = {}
    for key, (xmlid, quantity, estimate, sequence) in line_specs.items():
        lines[key] = _immutable_record(
            env, "sedar.purchase.request.line", xmlid, {
                "request_id": request.id,
                "sequence": sequence,
                "product_id": products[key].id,
                "quantity": quantity,
                "estimated_unit_price": estimate,
                "source_location_id": storage.id,
                "need_reason": "Required physical stock for the scheduled service cycle.",
            },
            identity_fields=("request_id", "product_id"),
        )
    if request.state == "draft":
        request.with_user(officer).action_submit()
    if request.state == "submitted":
        request.with_user(officer).action_approve()
    return request, lines


def _ensure_pm_bids(env, officer, request, request_lines, bidders):
    specs = {
        "one": (
            "pm_bid_1", ("a", "b"), (780.0, 305.0),
            "Combined delivery in seven days; stock confirmed.",
        ),
        "two": (
            "pm_bid_2", ("a",), (745.0,),
            "Filter set available in fourteen days.",
        ),
        "three": (
            "pm_bid_3", ("b", "c"), (330.0, 179500.0),
            "Pump includes commissioning support and twelve-month warranty.",
        ),
    }
    bids = {}
    for key, (xmlid, line_keys, prices, notes) in specs.items():
        bid = _immutable_record(
            env, "sedar.purchase.bid", xmlid, {
                "request_id": request.id,
                "bidder_id": bidders[key].id,
                "received_date": date(2026, 8, 20),
                "validity_date": UNBOUNDED_BID_VALIDITY,
                "promised_delivery_date": date(2026, 8, 29),
                "delivery_terms": "Delivered to SEDAR Storage, Batangas.",
                "availability_notes": notes,
                "payment_terms": "Thirty days from accepted delivery.",
                "warranty_notes": "Manufacturer warranty applies.",
                "commercial_notes": (
                    "Fictional quotation for the approved PM demonstration."
                ),
                "quotation_filename": f"{xmlid}-quotation.txt",
                "quotation_file": base64.b64encode(
                    f"SEDAR DEMO QUOTATION — {bidders[key].name}\n".encode()
                ),
                "line_ids": [
                    Command.create({
                        "request_line_id": request_lines[line_key].id,
                        "unit_price": price,
                        "availability_note": notes,
                    })
                    for line_key, price in zip(line_keys, prices)
                ],
            },
            identity_fields=("request_id", "bidder_id"),
        )
        if bid.state == "draft":
            bid.with_user(officer).action_receive()
        bids[key] = bid
        _bind_pm_bid_children(env, key, bid, line_keys, request_lines)
    return bids


def _bind_pm_bid_children(env, bidder_key, bid, line_keys, request_lines):
    for line_key in line_keys:
        bid_line = bid.line_ids.filtered(
            lambda line, key=line_key: line.request_line_id == request_lines[key]
        )
        _bind_xmlid(env, f"pm_bid_line_{bidder_key}_{line_key}", bid_line)
    attachment = env["ir.attachment"].sudo().search([
        ("res_model", "=", "sedar.purchase.bid"),
        ("res_id", "=", bid.id),
        ("res_field", "=", "quotation_file"),
    ], limit=1)
    if attachment:
        _bind_xmlid(env, f"pm_bid_{bidder_key}_quotation", attachment)


def _ensure_pm_awards(env, officer, request_lines, bids):
    winners = {
        "a": (
            bids["one"],
            "Bidder 1 offers the best delivery and total service value.",
        ),
        "b": (
            bids["one"],
            "Bidder 1 consolidates Products A and B in one delivery.",
        ),
        "c": (
            bids["three"],
            "Bidder 3 provides the required pump warranty and support.",
        ),
    }
    for key, (bid, reason) in winners.items():
        line = request_lines[key]
        award = line.sudo().current_award_id
        if not award:
            bid_line = bid.line_ids.filtered(
                lambda item: item.request_line_id == line
            )
            award = line.with_user(officer)._create_line_award(bid_line, reason)
        _bind_xmlid(env, f"pm_award_{key}", award)


def _ensure_pm_orders(env, officer, request, bids, products):
    request.with_user(officer).action_create_purchase_orders()
    product_keys = {product.id: key for key, product in products.items()}
    orders = {}
    for key in ("one", "three"):
        order = request.sudo().purchase_order_ids.filtered(
            lambda item, bid=bids[key]: item.sedar_bid_id == bid
        )
        _bind_xmlid(env, f"pm_purchase_order_bidder_{key}", order)
        for line in order.order_line:
            product_key = product_keys[line.product_id.id]
            _bind_xmlid(env, f"pm_purchase_order_line_{product_key}", line)
        orders[key] = order
    return orders


def _ensure_pm_receipts(env, orders, products):
    replacement_lot = _immutable_record(env, "stock.lot", "pm_product_c_serial", {
        "name": "DEMO-CWP-500-0001",
        "product_id": products["c"].id,
        "company_id": env.company.id,
    }, identity_fields=("company_id", "product_id", "name"))
    for key, order in orders.items():
        if order.state in {"draft", "sent"}:
            order.button_confirm()
        for picking in order.picking_ids.filtered(
            lambda item: item.state not in {"done", "cancel"}
        ):
            picking.action_confirm()
            picking.action_assign()
            for move_line in picking.move_line_ids:
                if move_line.product_id == products["c"]:
                    move_line.lot_id = replacement_lot
                move_line.quantity = move_line.move_id.product_uom_qty
            result = picking.button_validate()
            if (
                isinstance(result, dict)
                and result.get("res_model") == "stock.immediate.transfer"
            ):
                env[result["res_model"]].with_context(
                    **result.get("context", {})
                ).create({}).process()
        done_picking = order.picking_ids.filtered(
            lambda item: item.state == "done"
        )[:1]
        if done_picking:
            _bind_xmlid(env, f"pm_receipt_bidder_{key}", done_picking)


def _ensure_pm_current_use(env, officer, product, tugboat):
    identity = {
        "company_id": env.company.id,
        "product_id": product.id,
        "tugboat_id": tugboat.id,
    }
    issue = _resolve_immutable_record(
        env,
        "sedar.inventory.issue",
        "pm_inventory_issue_a",
        identity,
        identity_fields=("company_id", "product_id", "tugboat_id"),
    )
    if not issue:
        issue = env["sedar.inventory.issue"].with_user(officer)._issue_to_tug(
            product,
            tugboat,
            1.0,
            "Issue Product A to STS Atlas for the due main-engine service.",
        )
        _bind_xmlid(env, "pm_inventory_issue_a", issue)
    _bind_xmlid(env, "pm_inventory_issue_move_a", issue.stock_move_id)
    _bind_xmlid(env, "pm_inventory_lifecycle_a", issue.lifecycle_id)


def _bind_pm_maintenance_facts(env, equipment):
    baseline = env.ref(
        "sedar_marine_maintenance.atlas_main_engine_reading_service_1000",
        raise_if_not_found=False,
    )
    current = env.ref(
        "sedar_marine_maintenance.atlas_main_engine_reading_current_1510",
        raise_if_not_found=False,
    )
    if baseline:
        _bind_xmlid(env, "pm_running_hour_baseline", baseline)
    if current:
        _bind_xmlid(env, "pm_running_hour_current", current)
    due_activity = equipment.sedar_pm_task_ids.sedar_open_alerts()[:1]
    if due_activity:
        _bind_xmlid(env, "pm_due_maintenance_activity", due_activity)


def _ensure_broader_demo_data(env):
    """Add moderate list/dashboard volume without changing source-of-truth rules."""
    _ensure_customer_breadth(env)
    _ensure_inventory_breadth(env)
    _ensure_service_order_breadth(env)
    _ensure_invoice_breadth(env)
    _ensure_maintenance_breadth(env)
    _ensure_purchase_request_breadth(env)
    _ensure_hsse_breadth(env)
    _ensure_document_breadth(env)


def _ensure_customer_breadth(env):
    existing_clients = [
        env.ref(f"sedar_service_order_demo.client_{code}", raise_if_not_found=False)
        for code in ("archipelago", "baylink", "pacific", "island")
    ]
    for client in filter(None, existing_clients):
        if client.customer_rank < 1:
            client.customer_rank = 1
    client_specs = [
        ("northstar", "Northstar Coastal Shipping, Inc.", "9881201", "MV Northstar Pioneer"),
        ("seabridge", "SeaBridge Bulk Carriers Corporation", "9881202", "MV SeaBridge Valor"),
        ("harborline", "HarborLine Petroleum Logistics, Inc.", "9881203", "MT HarborLine One"),
        ("orient", "Orient Inter-Island Transport Corporation", "9881204", "MV Orient Voyager"),
    ]
    for index, (code, name, imo, vessel_name) in enumerate(client_specs, start=1):
        client = _record(env, "res.partner", f"executive_client_{code}", {
            "name": name,
            "is_company": True,
            "company_type": "company",
            "customer_rank": 1,
            "email": f"operations@{code}.example.com",
            "phone": f"+63 2 8890 20{index:02d}",
            "city": "Batangas City",
            "country_id": env.ref("base.ph").id,
        })
        _record(env, "res.partner", f"executive_client_{code}_contact", {
            "name": f"Demo Operations Contact {index + 4}",
            "parent_id": client.id,
            "email": f"dispatch@{code}.example.com",
            "phone": f"+63 917 620 {index:04d}",
        })
        _record(env, "sedar.client.vessel", f"executive_client_{code}_vessel", {
            "name": vessel_name,
            "owner_id": client.id,
            "vessel_type": "tanker" if code == "harborline" else "cargo",
            "imo_number": imo,
            "call_sign": f"DU{imo[-4:]}",
            "gross_tonnage": 16000 + index * 3200,
            "length_overall": 138 + index * 9,
            "draft": 7.2 + index * 0.4,
        })


def _ensure_inventory_breadth(env):
    company = env.company
    warehouse = _first(env, "stock.warehouse", [("company_id", "=", company.id)])
    if not warehouse:
        return
    stock_location = warehouse.lot_stock_id
    unit = env.ref("uom.product_uom_unit")
    liter = env.ref("uom.product_uom_litre", raise_if_not_found=False) or unit
    products = [
        ("battery", "Demo Marine Battery 24V", "SEDAR-SP-BATT24", "BAT-24V-200AH", unit.id, 8, 4),
        ("rope", "Demo Mooring Rope 48mm", "SEDAR-DECK-ROPE48", "MR-48MM-220M", unit.id, 18, 6),
        ("paint", "Demo Marine Antifouling Paint", "SEDAR-MNT-PAINT", "AF-PNT-20L", liter.id, 120, 40),
        ("zinc", "Demo Zinc Anode Set", "SEDAR-SP-ANODE", "ZN-ANODE-SET", unit.id, 30, 10),
        ("radar", "Demo Radar Display Fuse", "SEDAR-NAV-FUSE", "RDR-FUSE-15A", unit.id, 2, 5),
        ("valve", "Demo Cooling Water Valve", "SEDAR-SP-CWVALVE", "CWV-50MM-BR", unit.id, 6, 3),
        ("belt", "Demo Alternator Belt", "SEDAR-SP-BELT", "ALT-BLT-B76", unit.id, 16, 8),
        ("grease", "Demo Marine Grease Cartridge", "SEDAR-LUBE-GREASE", "MG-EP2-400G", unit.id, 90, 30),
        ("extinguisher", "Demo Fire Extinguisher 9kg", "SEDAR-HSSE-FE9", "FE-DRY-9KG", unit.id, 4, 6),
        ("ppe", "Demo Deck Crew PPE Kit", "SEDAR-HSSE-PPE", "PPE-DECK-KIT", unit.id, 22, 12),
        ("chart", "Demo Navigation Chart Pack", "SEDAR-NAV-CHART", "NAV-BTG-2026", unit.id, 10, 3),
        ("hydraulic", "Demo Hydraulic Oil", "SEDAR-LUBE-HYD", "HYD-AW68", liter.id, 300, 120),
        ("impeller", "Demo Seawater Pump Impeller", "SEDAR-SP-IMPELLER", "IMP-SWP-90", unit.id, 1, 4),
        ("gasket", "Demo Exhaust Gasket Set", "SEDAR-SP-GASKET", "EX-GKT-SET", unit.id, 9, 5),
        ("radio", "Demo Handheld VHF Radio", "SEDAR-NAV-VHF", "VHF-HH-IP67", unit.id, 5, 4),
    ]
    for xmlid, name, code, part_number, uom_id, quantity, reorder_point in products:
        product_data = env["ir.model.data"].search([
            ("module", "=", "sedar_demo_suite"),
            ("name", "=", f"inventory_item_{xmlid}"),
        ], limit=1)
        existing_product = (
            env["product.product"].browse(product_data.res_id).exists()
            if product_data else env["product.product"]
        )
        product = _record(env, "product.product", f"inventory_item_{xmlid}", {
            "name": name,
            "type": "consu",
            "is_storable": True,
            "uom_id": uom_id,
            "default_code": code,
            "sedar_inventory_item": True,
            "sedar_manufacturer_part_number": part_number,
            "sedar_compatibility_scope": "fleet",
            "sedar_reorder_point": reorder_point,
        })
        if not existing_product and quantity:
            env["stock.quant"]._update_available_quantity(
                product, stock_location, quantity
            )

    manager = env.ref("sedar_purchase_request.user_procurement_manager", raise_if_not_found=False)
    tugboats = env["sedar.tugboat"].search([], order="id", limit=3)
    for index, tugboat in enumerate(tugboats, start=1):
        product = env.ref("sedar_demo_suite.inventory_item_ppe", raise_if_not_found=False)
        if manager and product:
            _ensure_inventory_issue(env, f"inventory_issue_ppe_{index}", product, tugboat, 1, "Demo PPE replenishment for tug crew readiness.", manager)


def _ensure_inventory_lifecycle_demo(env):
    """Seed the approved quantity-tracked Tow Rope walkthrough starting state."""
    company = env.company
    tug_class = _first(env, "sedar.tug.class")
    home_port = _first(env, "sedar.marine.port")
    if not tug_class:
        return
    tugs = []
    for index, status in ((1, "maintenance"), (2, "available"), (3, "available")):
        tugs.append(_record(env, "sedar.tugboat", f"inventory_sedar_{index}", {
            "name": f"SEDAR {index}",
            "company_id": company.id,
            "registration_number": f"SEDAR-DEMO-{index}",
            "call_sign": f"SDR{index}",
            "tug_class_id": tug_class.id,
            "bollard_pull": tug_class.minimum_bollard_pull or 30,
            "fuel_capacity": 25000,
            "home_port_id": home_port.id if home_port else False,
            "availability_status": status,
        }))
    from odoo.addons.sedar_marine_inventory.hooks import post_init_hook
    post_init_hook(env)
    unit = env.ref("uom.product_uom_unit")
    rope_data = _fixture_data(env, "inventory_item_tow_rope_80")
    existing_rope = bool(
        rope_data
        and env["product.product"].browse(rope_data.res_id).exists()
    )
    rope = _record(env, "product.product", "inventory_item_tow_rope_80", {
        "name": "Tow Rope - 80 mm",
        "type": "consu",
        "is_storable": True,
        "uom_id": unit.id,
        "default_code": "SEDAR-GEAR-TOWROPE-80",
        "sedar_inventory_item": True,
        "sedar_item_type": "reusable_onboard_gear",
        "sedar_readiness_critical": True,
        "sedar_manufacturer_part_number": "TR-80MM-220M",
        "sedar_compatibility_scope": "fleet",
        "sedar_reorder_point": 1,
    })
    required = (3.0, 2.0, 2.0)
    for index, (tug, quantity) in enumerate(zip(tugs, required), start=1):
        _record(env, "sedar.tug.stock.requirement", f"tow_rope_requirement_{index}", {
            "company_id": company.id,
            "product_id": rope.id,
            "tugboat_id": tug.id,
            "required_qty": quantity,
            "active": True,
            "note": "Approved SEDAR Tow Rope inventory lifecycle walkthrough.",
        })
    marker = env["ir.config_parameter"].sudo().get_param(
        "sedar_demo_suite.inventory_lifecycle_seeded"
    )
    if not marker and not existing_rope:
        Quant = env["stock.quant"]
        for tug, quantity in zip(tugs, (3.0, 1.0, 2.0)):
            current = Quant._get_available_quantity(
                rope, tug.stock_location_id, strict=True
            )
            Quant._update_available_quantity(
                rope, tug.stock_location_id, quantity - current
            )
        warehouse = company.sedar_default_storage_location_id
        current = Quant._get_available_quantity(rope, warehouse, strict=True)
        if current:
            Quant._update_available_quantity(rope, warehouse, -current)
    if not marker:
        env["ir.config_parameter"].sudo().set_param(
            "sedar_demo_suite.inventory_lifecycle_seeded", "1"
        )
    env["sedar.replenishment.demand"]._sync_inventory_shortages()


def _ensure_inventory_issue(env, xmlid, product, tugboat, quantity, purpose, manager):
    data = env["ir.model.data"].search([
        ("module", "=", "sedar_demo_suite"),
        ("name", "=", xmlid),
    ], limit=1)
    if data and env["sedar.inventory.issue"].browse(data.res_id).exists():
        return data.res_id
    if data:
        data.unlink()
    issue = env["sedar.inventory.issue"].with_user(manager)._issue_to_tug(product, tugboat, quantity, purpose)
    env["ir.model.data"].create({
        "module": "sedar_demo_suite",
        "name": xmlid,
        "model": "sedar.inventory.issue",
        "res_id": issue.id,
        "noupdate": True,
    })
    return issue.id


def _ensure_inventory_shortage_demo(env):
    """Keep one stock-derived Job Order shortage available for Procurement QA."""
    order = env.ref("sedar_service_order_demo.order_missing_engineer", raise_if_not_found=False)
    product = env.ref("sedar_marine_inventory.product_pump_packing", raise_if_not_found=False)
    warehouse = _first(env, "stock.warehouse", [("company_id", "=", env.company.id)])
    if not order or not product or not warehouse:
        return

    requirement = _record(env, "sedar.inventory.requirement", "job_order_inventory_shortage", {
        "order_id": order.id,
        "product_id": product.id,
        "source_location_id": warehouse.lot_stock_id.id,
        "expected_consumption_qty": 1.0,
        "auto_generated": False,
        "note": "Demo shortage: tug-compatible pump packing is unavailable for STS Lakas.",
    })
    requirement._compute_stock_status()
    order._sync_inventory_readiness()
    order.sync_automated_readiness()


def _ensure_service_order_breadth(env):
    clients = env["res.partner"].search([("is_company", "=", True), ("customer_rank", ">", 0)], order="id", limit=8)
    if not clients:
        clients = env["res.partner"].search([("is_company", "=", True)], order="id", limit=8)
    vessels = env["sedar.client.vessel"].search([], order="id")
    services = env["sedar.marine.service.type"].search([], order="id")
    port = env.ref("sedar_marine_operations.port_batangas", raise_if_not_found=False) or _first(env, "sedar.marine.port")
    terminal = env.ref("sedar_marine_operations.berth_batangas_base", raise_if_not_found=False) or _first(env, "sedar.marine.berth")
    anchorage = env.ref("sedar_marine_operations.berth_batangas_anchorage", raise_if_not_found=False) or terminal
    tug_class = _first(env, "sedar.tug.class")
    if not all([clients, vessels, services, port, terminal]):
        return
    states = ["draft", "submitted", "review", "quoted", "confirmed", "planning", "blocked", "cancelled", "submitted"]
    today = date.today()
    for index in range(70):
        client = clients[index % len(clients)]
        vessel = vessels[index % len(vessels)]
        service = services[index % len(services)]
        state = states[index % len(states)]
        service_day = today - timedelta(days=(index * 7) % 90)
        if index % 14 == 0:
            service_day = today + timedelta(days=index % 6 + 1)
        requested_start = datetime(
            service_day.year, service_day.month, service_day.day, 6 + (index % 12), 0, 0
        )
        order = _record(env, "sedar.marine.service.order", f"enriched_order_{index + 1:02d}", {
            "client_id": client.id,
            "contact_id": _first(env, "res.partner", [("parent_id", "=", client.id)]).id,
            "request_channel": ["portal", "email", "phone", "internal"][index % 4],
            "client_reference": f"DEMO-ENR-SO-{index + 1:03d}",
            "priority": "urgent" if index % 5 == 0 else "normal",
            "assisted_vessel_id": vessel.id,
            "assisted_vessel_name": vessel.name,
            "service_type_id": service.id,
            "number_of_tugs": 2 if index % 6 == 0 else 1,
            "tug_class_id": tug_class.id if tug_class else False,
            "required_bollard_pull": tug_class.minimum_bollard_pull if tug_class else 30,
            "scope_of_work": "Enriched demonstration service order for dashboard volume.",
            "special_instructions": "Demo-only scenario for proposal walkthrough.",
            "port_id": port.id,
            "terminal_id": terminal.id,
            "origin_berth_id": anchorage.id,
            "destination_berth_id": terminal.id,
            "requested_start": requested_start,
            "estimated_duration_hours": 2 + (index % 5),
            "state": state,
        })
        if state in {"quoted", "confirmed", "planning", "blocked"}:
            order._freeze_pricing()


def _ensure_invoice_breadth(env):
    sale_journal = _first(env, "account.journal", [("type", "=", "sale")])
    product = env.ref("sedar_marine_finance.product_marine_service", raise_if_not_found=False)
    clients = env["res.partner"].search([("is_company", "=", True), ("customer_rank", ">", 0)], order="id", limit=8)
    if not sale_journal or not product or not clients:
        return
    today = date.today()
    for index in range(15):
        invoice_day = today - timedelta(days=8 + index * 5)
        invoice = _record(env, "account.move", f"enriched_customer_invoice_{index + 1:02d}", {
            "move_type": "out_invoice",
            "journal_id": sale_journal.id,
            "partner_id": clients[index % len(clients)].id,
            "invoice_date": invoice_day,
            "invoice_date_due": invoice_day + timedelta(days=30),
            "invoice_origin": f"DEMO-ENR-SO-{index + 1:03d}",
            "ref": f"DEMO-ENR-INV-{index + 1:03d}",
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "name": f"Demo marine tug service package {index + 1}",
                "quantity": 1.0,
                "price_unit": 18000 + index * 2750,
            })],
        }, update=False)
        if invoice.state == "draft":
            invoice.action_post()


def _ensure_maintenance_breadth(env):
    company = env.company
    team = env.ref("sedar_marine_maintenance.team_marine_technical", raise_if_not_found=False) or _record(env, "maintenance.team", "enriched_maintenance_team", {
        "name": "Demo Marine Technical",
        "company_id": company.id,
    })
    category = env.ref("sedar_marine_maintenance.category_tugboat_systems", raise_if_not_found=False) or _first(env, "maintenance.equipment.category")
    tugboats = env["sedar.tugboat"].search([], order="id")
    if not tugboats or not team:
        return
    work_types = ["planned", "defect", "drydock"]
    impacts = ["none", "advisory", "blocking"]
    today = date.today()
    for index in range(17):
        tugboat = tugboats[index % len(tugboats)]
        equipment = _record(env, "maintenance.equipment", f"enriched_equipment_{index + 1:02d}", {
            "name": f"{tugboat.name} Demo Equipment {index + 1}",
            "category_id": category.id if category else False,
            "maintenance_team_id": team.id,
            "sedar_tugboat_id": tugboat.id,
            "sedar_system": ["propulsion", "electrical", "navigation", "deck", "safety"][index % 5],
            "sedar_criticality": ["minor", "major", "critical"][index % 3],
            "sedar_installation_date": "2025-01-15",
        })
        _record(env, "sedar.pm.task", f"enriched_pm_task_{index + 1:02d}", {
            "name": "Scheduled service",
            "equipment_id": equipment.id,
            "interval_hours": 250 + index * 50,
        })
        request = _record(env, "maintenance.request", f"enriched_work_order_{index + 1:02d}", {
            "name": f"Demo Maintenance - {tugboat.name} scenario {index + 1}",
            "maintenance_type": "preventive" if index % 3 == 0 else "corrective",
            "equipment_id": equipment.id,
            "maintenance_team_id": team.id,
            "schedule_date": datetime.combine(
                today - timedelta(days=(index * 5) % 75), datetime.min.time()
            ).replace(hour=8),
            "duration": 2 + (index % 6),
            "priority": str((index % 3) + 1),
            "sedar_tugboat_id": tugboat.id,
            "sedar_work_order_type": work_types[index % len(work_types)],
            "sedar_availability_impact": impacts[index % len(impacts)],
            "sedar_priority": ["low", "medium", "high"][index % 3],
            "sedar_defect_source": "Demo inspection note" if index % 3 else False,
            "sedar_spare_part_note": "Demo spare part planning note.",
        })
        if index in {1, 5} and not request.close_date:
            request.write({
                "close_date": datetime.combine(
                    today - timedelta(days=max(index - 1, 0)), datetime.min.time()
                ).replace(hour=15),
                "sedar_closure_note": "Demo work order closed after verification.",
            })


def _ensure_purchase_request_breadth(env):
    manager = env.ref("sedar_purchase_request.user_procurement_manager", raise_if_not_found=False)
    products = env["product.product"].search([("sedar_inventory_item", "=", True)], order="id")
    location = _first(env, "stock.warehouse", [("company_id", "=", env.company.id)]).lot_stock_id
    if not manager or not products or not location:
        return
    states = ["draft", "submitted", "approved", "submitted", "draft", "approved", "submitted", "draft"]
    for index, state in enumerate(states, start=1):
        request = _record(env, "sedar.purchase.request", f"enriched_purchase_request_{index:02d}", {
            "requester_id": manager.id,
            "source_type": ["inventory", "maintenance", "operations", "manual"][index % 4],
            "required_date": datetime(2026, 8, 20 + index, 9, 0, 0),
            "priority": ["normal", "urgent", "emergency"][index % 3],
            "justification": "Enriched demonstration purchase request for procurement queue volume.",
            "state": "draft",
        }, update=False)
        if not request.line_ids:
            _record(env, "sedar.purchase.request.line", f"enriched_purchase_request_{index:02d}_line", {
                "request_id": request.id,
                "product_id": products[(index - 1) % len(products)].id,
                "quantity": 2 + index,
                "estimated_unit_price": 500 + index * 125,
                "source_location_id": location.id,
                "need_reason": "Demo replenishment requirement.",
            }, update=False)
        if request.state == "draft" and state in {"submitted", "approved"}:
            request.with_user(manager).action_submit()
        if request.state == "submitted" and state == "approved":
            request.with_user(manager).action_approve()


def _ensure_hsse_breadth(env):
    manager = env.ref("sedar_hsse.user_hsse_manager", raise_if_not_found=False)
    tugboats = env["sedar.tugboat"].search([], order="id")
    orders = env["sedar.marine.service.order"].search([], order="id")
    berth = _first(env, "sedar.marine.berth")
    if not manager:
        return
    incident_states = ["reported", "investigating", "action_required", "verified", "reported", "investigating", "verified", "action_required"]
    for index, state in enumerate(incident_states, start=1):
        close_values = {}
        if state == "verified":
            close_values = {
                "closed_by_id": manager.id,
                "closed_at": datetime(2026, 8, 10 + index, 13, 0, 0),
                "verified_by_id": manager.id,
                "verified_at": datetime(2026, 8, 10 + index, 14, 0, 0),
            }
        incident = _record(env, "sedar.hsse.incident", f"enriched_hsse_incident_{index:02d}", {
            "incident_type": ["near_miss", "incident", "unsafe_condition"][index % 3],
            "category": ["operation", "vessel", "environment", "security"][index % 4],
            "severity": ["low", "medium", "high", "critical"][index % 4],
            "occurrence_datetime": datetime(2026, 8, 5 + index, 8 + index, 0, 0),
            "reported_by_id": manager.id,
            "investigator_id": manager.id if state in {"investigating", "action_required", "verified"} else False,
            "service_order_id": orders[(index - 1) % len(orders)].id if orders else False,
            "tugboat_id": tugboats[(index - 1) % len(tugboats)].id if tugboats else False,
            "berth_id": berth.id if berth else False,
            "summary": f"Enriched demo HSSE scenario {index}.",
            "immediate_action": "Area made safe and supervisor notified.",
            "investigation_summary": "Demo investigation notes for management review." if state in {"action_required", "verified"} else False,
            "root_cause": "Demo root cause pending validation." if state in {"action_required", "verified"} else False,
            "confidential": index % 2 == 0,
            "state": state,
            **close_values,
        }, update=False)
        if state in {"action_required", "investigating"}:
            _record(env, "sedar.hsse.corrective.action", f"enriched_hsse_action_{index:02d}", {
                "name": f"Demo corrective action {index}",
                "incident_id": incident.id,
                "assigned_user_id": manager.id,
                "due_date": date.today() + timedelta(days=index - 3),
                "severity": "critical" if index % 4 == 0 else "high",
                "critical_control": index % 4 == 0,
                "description": "Demo corrective action for HSSE dashboard volume.",
                "state": "open",
            }, update=False)


def _ensure_document_breadth(env):
    owner = env.ref("sedar_executive_dashboard.user_executive_demo", raise_if_not_found=False) or env.user
    document_types = env["sedar.document.type"].search([], order="id")
    tugs = env["sedar.tugboat"].search([], order="id")
    clients = env["res.partner"].search([("is_company", "=", True)], order="id", limit=5)
    if not document_types:
        return
    categories = ["corporate", "vessel", "commercial", "hse", "hr"]
    for index in range(12):
        document_type = document_types[index % len(document_types)]
        reference = f"DEMO-DOC-{index + 1:03d}"
        _record(env, "sedar.document", f"enriched_document_{index + 1:02d}", {
            "name": f"Demo Controlled Document {index + 1}",
            "document_type_id": document_type.id,
            "file": base64.b64encode((f"SEDAR DEMO CONTROLLED DOCUMENT\n{reference}\n").encode()).decode(),
            "filename": f"{reference}.txt",
            "state": "active",
            "notes": "Enriched demonstration controlled document.",
            "document_category": categories[index % len(categories)],
            "owner_id": owner.id,
            "valid_from": date(2026, 1, 1),
            "valid_until": date.today() + timedelta(days=15 + index * 20),
            "renewal_date": date.today() + timedelta(days=5 + index * 20),
            "approval_state": "approved",
            "confidential": index % 4 == 0,
            "partner_id": clients[index % len(clients)].id if clients else False,
            "tugboat_id": tugs[index % len(tugs)].id if tugs and index % 2 else False,
        })

"""Final, repeatable reconciliation for the complete fictional demonstration."""


def post_init_hook(env):
    company = env.company
    company.sedar_configure_demo_currency()
    company.sedar_ensure_erp_demo()
    company.sedar_ensure_recruitment_demo()
    company.sedar_ensure_crew_onboarding_demo()
    company.sedar_ensure_executive_demo()

    from odoo.addons.sedar_service_order_demo.hooks import post_init_hook as reconcile_orders
    from odoo.addons.sedar_marine_dispatch_demo.hooks import post_init_hook as reconcile_dispatch
    from odoo.addons.sedar_marine_inventory.hooks import post_init_hook as reconcile_inventory
    from odoo.addons.sedar_marine_maintenance.hooks import post_init_hook as reconcile_maintenance
    from odoo.addons.sedar_purchase_request.hooks import post_init_hook as reconcile_purchase

    for reconciler in (reconcile_orders, reconcile_dispatch, reconcile_inventory, reconcile_maintenance, reconcile_purchase):
        reconciler(env)

    company.sedar_ensure_erp_demo()
    # The ERP module can be initialized before service-demo partners and
    # products exist. Re-run the accounting portion after reconciliation.
    company._sedar_ensure_accounting_demo(company)
    _ensure_paid_service_demo(env)
    _ensure_procurement_demo(env)
    company.sedar_ensure_executive_demo()
    return True


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


def _ensure_procurement_demo(env):
    manager = env.ref("sedar_purchase_request.user_procurement_manager", raise_if_not_found=False)
    request = env.ref("sedar_purchase_request.request_demo_spare_parts", raise_if_not_found=False)
    if not manager or not request:
        return
    request = request.with_user(manager)
    if request.state == "submitted":
        request.action_approve()
    if not request.purchase_order_id:
        request.action_create_rfq()
    order = request.purchase_order_id
    if not order:
        return
    order = order.with_user(manager)
    if order.state in {"draft", "sent"}:
        order.button_confirm()
    for picking in order.picking_ids.filtered(lambda item: item.state not in {"done", "cancel"}):
        picking.action_confirm()
        picking.action_assign()
        for move_line in picking.move_line_ids:
            move_line.quantity = move_line.move_id.product_uom_qty
        result = picking.button_validate()
        if isinstance(result, dict) and result.get("res_model") == "stock.immediate.transfer":
            env[result["res_model"]].with_context(**result.get("context", {})).create({}).process()
    if order.invoice_status == "to invoice" and not order.invoice_ids:
        order.action_create_invoice()
    accounting_user = env.ref("sedar_service_order_demo.user_accounting_manager", raise_if_not_found=False)
    for bill in order.invoice_ids.filtered(lambda item: item.state == "draft"):
        bill.invoice_date = "2026-08-18"
        (bill.with_user(accounting_user) if accounting_user else bill).action_post()

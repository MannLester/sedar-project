from datetime import datetime


MODULE = "sedar_marine_dispatch_demo"


def _record(env, model, xmlid, values):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid)
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            record.with_context(sedar_demo_reconcile=True).write(values)
            return record
        data.unlink()
    record = env[model].create(values)
    env["ir.model.data"].create({
        "module": MODULE, "name": xmlid, "model": model,
        "res_id": record.id, "noupdate": True,
    })
    return record


def _dt(day, hour, minute=0):
    return datetime(2026, 8, day, hour, minute)


def post_init_hook(env):
    ready_order = env.ref("sedar_service_order_demo.order_ready")
    completed_order = env.ref("sedar_service_order_demo.order_completed")
    two_tug_order = env.ref("sedar_service_order_demo.order_two_tug")

    ready_order.with_context(sedar_readiness_sync=True).write({
        "inventory_ready": True,
        "inventory_ready_by_id": env.user.id,
        "inventory_ready_at": _dt(10, 6, 45),
    })
    ready_order._sync_automated_readiness()
    ready_operation = ready_order.operation_ids[:1]
    _record(env, "sedar.marine.operation.log", "log_ready_planning", {
        "operation_id": ready_operation.id,
        "event_time": _dt(10, 7), "event_type": "general",
        "description": "Operation created and awaiting dispatch authorization.",
        "client_visible": False,
    })

    completed_order.with_context(sedar_readiness_sync=True).write({
        "state": "completed",
        "inventory_ready": True,
        "inventory_ready_by_id": env.user.id,
        "inventory_ready_at": _dt(3, 6),
    })
    _reconcile_demo_completions(completed_order, _dt(3, 8), _dt(3, 11))
    completed_operation = _record(env, "sedar.marine.operation", "operation_completed", {
        "order_id": completed_order.id,
    })
    completed_operation.tug_operation_ids.write({
        "state": "returned", "departed_base_at": _dt(3, 7),
        "arrived_on_scene_at": _dt(3, 8), "service_released_at": _dt(3, 10),
        "returned_base_at": _dt(3, 11),
    })
    completed_operation.write({
        "state": "completed", "dispatcher_id": env.user.id,
        "dispatch_time": _dt(3, 6, 30), "actual_start": _dt(3, 8),
        "actual_end": _dt(3, 11),
        "completion_summary": "Demonstration harbor assistance completed without incident.",
        "client_representative": "Demo Client Operations Contact",
        "client_confirmation_time": _dt(3, 11, 30),
    })
    _record(env, "sedar.marine.operation.log", "log_completed_departed", {
        "operation_id": completed_operation.id, "event_time": _dt(3, 7),
        "event_type": "tug_departed", "description": "STS Matikas departed SEDAR Base.",
        "client_visible": True,
    })
    _record(env, "sedar.marine.operation.log", "log_completed_service", {
        "operation_id": completed_operation.id, "event_time": _dt(3, 8),
        "event_type": "service_started", "description": "Harbor assistance commenced.",
        "client_visible": True,
    })
    _record(env, "sedar.marine.operation.log", "log_completed_returned", {
        "operation_id": completed_operation.id, "event_time": _dt(3, 11),
        "event_type": "tugs_returned", "description": "STS Matikas returned to SEDAR Base.",
        "client_visible": True,
    })
    _record(env, "sedar.marine.operation.delay", "delay_completed_port", {
        "operation_id": completed_operation.id, "category": "port",
        "responsible_party": "port", "start_time": _dt(3, 8, 30),
        "end_time": _dt(3, 9), "description": "Demonstration port traffic delay.",
        "state": "resolved", "client_visible": True,
    })

    # The flagship two-tug scenario must exercise the same operational handoff
    # as the single-tug scenario.  Keep it deterministic and idempotent so a
    # module upgrade repairs an existing demo database as well as a fresh one.
    two_tug_order.with_context(sedar_readiness_sync=True).write({
        "state": "completed",
        "inventory_ready": True,
        "inventory_ready_by_id": env.user.id,
        "inventory_ready_at": _dt(14, 6),
    })
    _reconcile_demo_completions(two_tug_order, _dt(14, 8), _dt(14, 13))
    two_tug_operation = _record(env, "sedar.marine.operation", "operation_two_tug", {
        "order_id": two_tug_order.id,
    })
    two_tug_operation.tug_operation_ids.write({
        "state": "returned", "departed_base_at": _dt(14, 7),
        "arrived_on_scene_at": _dt(14, 8), "service_released_at": _dt(14, 12),
        "returned_base_at": _dt(14, 13),
    })
    two_tug_operation.write({
        "state": "completed", "dispatcher_id": env.user.id,
        "dispatch_time": _dt(14, 6, 30), "actual_start": _dt(14, 8),
        "actual_end": _dt(14, 13),
        "completion_summary": "Demonstration two-tug towage completed without incident.",
        "client_representative": "Demo Client Operations Contact",
        "client_confirmation_time": _dt(14, 13, 30),
    })


def _reconcile_demo_completions(order, actual_start, actual_end):
    for assignment in order.tug_assignment_ids.filtered(lambda item: item.state != "cancelled"):
        if assignment.completion_state == "submitted":
            continue
        master = assignment.requirement_ids.filtered(lambda item: item.rank_id.code == "MASTER").mapped(
            "crew_assignment_ids.crew_profile_id"
        )[:1]
        assignment.with_context(sedar_completion_action=True).write({
            "actual_start": actual_start,
            "actual_end": actual_end,
            "completion_note": "Demo Tug Master completion declaration.",
            "completion_state": "submitted",
            "completion_declared_by_id": master.employee_id.user_id.id if master and master.employee_id.user_id else False,
            "completion_declared_at": actual_end,
        })

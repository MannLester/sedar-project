from datetime import datetime


MODULE = "sedar_manpower_planning_demo"


def _record(env, model, xmlid, values):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid)
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            return record
        data.unlink()
    record = env[model].create(values)
    env["ir.model.data"].create({
        "module": MODULE, "name": xmlid, "model": model,
        "res_id": record.id, "noupdate": True,
    })
    return record


def _dt(day, hour=8):
    return datetime(2026, 8, day, hour)


def post_init_hook(env):
    department = env.ref("sedar_service_order_demo.department_operations")
    careers_location = _record(env, "sedar.careers.location", "location_batangas", {
        "name": "Batangas City",
    })
    chief_engineer_job = env.ref("sedar_service_order_demo.job_cheng")
    missing_engineer = env.ref("sedar_service_order_demo.shortage_missing_engineer_cheng")
    expired_medical = env.ref("sedar_service_order_demo.shortage_expired_medical")

    missing_engineer.write({
        "review_state": "escalated", "root_cause": "permanent_headcount",
        "resolution_action": "manpower_request", "reviewer_id": env.user.id,
        "reviewed_at": _dt(15, 9),
        "resolution_notes": "No qualified Chief Engineer is available for recurring towage demand.",
    })
    request = _record(env, "sedar.manpower.request", "request_chief_engineer", {
        "department_id": department.id, "requested_by": env.user.id,
        "request_date": "2026-08-15", "priority": "urgent",
        "business_justification": "Recurring Chief Engineer shortage prevents reliable towage staffing.",
        "operational_impact": "Service orders may remain blocked or require unplanned substitutions.",
        "state": "position_open", "submitted_at": _dt(15, 10),
        "approved_at": _dt(16, 10), "hr_reviewer_id": env.user.id,
        "operations_approver_id": env.user.id,
    })
    line = _record(env, "sedar.manpower.request.line", "request_chief_engineer_line", {
        "request_id": request.id, "crew_rank_id": missing_engineer.rank_id.id,
        "job_id": chief_engineer_job.id, "request_type": "permanent", "quantity": 1,
        "approved_quantity": 1, "required_date": "2026-09-01",
        "shortage_ids": [(6, 0, [missing_engineer.id])],
        "required_certificate_type_ids": [(6, 0, missing_engineer.requirement_id.required_certificate_type_ids.ids)],
        "minimum_experience_years": 2,
        "required_qualifications": "Valid engineer competency certification and marine service experience.",
    })
    vacancy = _record(env, "sedar.job.vacancy", "vacancy_chief_engineer", {
        "request_line_id": line.id, "job_id": chief_engineer_job.id,
        "crew_rank_id": line.crew_rank_id.id, "department_id": department.id,
        "employment_type": "permanent", "approved_openings": 1,
        "opening_date": "2026-08-16", "application_deadline": "2026-09-15",
        "website_title": "Chief Engineer", "website_summary": "Join SEDAR's marine operations team.",
        "responsibilities": "Lead safe engine-room operations and maintain propulsion systems.",
        "requirements": line.required_qualifications, "website_location_id": careers_location.id,
        "publication_state": "published", "state": "open",
        "published_at": _dt(16, 11), "published_by_id": env.user.id,
    })
    line.vacancy_id = vacancy.id
    missing_engineer.manpower_request_line_id = line.id
    missing_engineer.write({"review_state": "escalated", "status": "open", "resolved_at": False})

    expired_medical.write({
        "review_state": "action_required", "root_cause": "medical",
        "resolution_action": "medical", "reviewer_id": env.user.id,
        "reviewed_at": _dt(12, 9),
        "resolution_notes": "Renew the assigned Chief Engineer's medical certificate.",
    })
    medical_action = _record(env, "sedar.crew.shortage.action", "action_expired_medical", {
        "shortage_id": expired_medical.id, "action_type": "medical",
        "responsible_user_id": env.user.id, "planned_date": "2026-08-20",
        "completed_date": "2026-08-19", "state": "completed",
        "outcome": "Medical renewal appointment completed; no new vacancy required.",
    })
    expired_medical.write({"review_state": "resolved", "status": "resolved", "resolved_at": _dt(19, 16)})

    leave_requirement = env["sedar.manning.requirement"].search([
        ("tug_assignment_id.order_id", "=", env.ref("sedar_service_order_demo.order_two_tug").id),
        ("rank_id.code", "=", "DECK"),
    ], limit=1)
    leave_shortage = _record(env, "sedar.crew.shortage", "shortage_leave_temporary", {
        "requirement_id": leave_requirement.id, "missing_count": 1, "reason": "leave",
        "review_state": "action_required", "root_cause": "leave",
        "resolution_action": "temporary_reliever", "reviewer_id": env.user.id,
        "reviewed_at": _dt(14, 9),
        "resolution_notes": "Assign a temporary reliever while the regular deckhand is on leave.",
    })
    _record(env, "sedar.crew.shortage.action", "action_leave_reliever", {
        "shortage_id": leave_shortage.id, "action_type": "replacement",
        "responsible_user_id": env.user.id, "planned_date": "2026-08-14",
        "completed_date": "2026-08-14", "state": "completed",
        "outcome": "Temporary reliever assigned from the available deckhand pool.",
    })
    leave_shortage.write({"review_state": "resolved", "status": "resolved", "resolved_at": _dt(14, 16)})

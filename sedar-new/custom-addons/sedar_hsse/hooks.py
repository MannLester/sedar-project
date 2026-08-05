from datetime import date, datetime, timedelta

from odoo import Command


MODULE = "sedar_hsse"


def _record(env, model, xmlid, values, update=True):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE),
        ("name", "=", xmlid),
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


def _first(env, model, domain=None):
    return env[model].search(domain or [], limit=1)


def post_init_hook(env):
    company = env.company
    manager = _record(env, "res.users", "user_hsse_manager", {
        "name": "Demo HSSE Manager",
        "login": "hsse@sedar.demo",
        "password": "hssedemo",
        "company_id": company.id,
        "company_ids": [Command.set([company.id])],
        "group_ids": [Command.set([
            env.ref("base.group_user").id,
            env.ref("sedar_hsse.group_sedar_hsse_manager").id,
        ])],
    }, update=False)

    employee = _first(env, "hr.employee")
    crew_profile = _first(env, "sedar.crew.profile")
    tugboat = _first(env, "sedar.tugboat")
    service_order = _first(env, "sedar.marine.service.order")
    operation = _first(env, "sedar.marine.operation")
    berth = service_order.origin_berth_id if service_order else _first(env, "sedar.marine.berth")
    maintenance_request = _first(env, "maintenance.request", [("sedar_tugboat_id", "!=", False)])

    incident = _record(env, "sedar.hsse.incident", "incident_demo_verified_near_miss", {
        "incident_type": "near_miss",
        "category": "operation",
        "severity": "high",
        "occurrence_datetime": datetime(2026, 8, 20, 9, 30, 0),
        "reported_by_id": manager.id,
        "investigator_id": manager.id,
        "service_order_id": service_order.id if service_order else False,
        "operation_id": operation.id if operation else False,
        "tugboat_id": tugboat.id if tugboat else False,
        "berth_id": berth.id if berth else False,
        "maintenance_request_id": maintenance_request.id if maintenance_request else False,
        "employee_ids": [Command.set([employee.id])] if employee else [Command.clear()],
        "crew_profile_ids": [Command.set([crew_profile.id])] if crew_profile else [Command.clear()],
        "summary": "Demo near miss during line handling at the berth.",
        "immediate_action": "Stopped the task, re-briefed the deck team, and checked PPE.",
        "investigation_summary": "The team identified a weak communication point during final line transfer.",
        "root_cause": "Hand signal confirmation was not consistently repeated before line movement.",
        "confidential": True,
        "state": "verified",
        "closed_by_id": manager.id,
        "closed_at": datetime(2026, 8, 21, 11, 0, 0),
        "verified_by_id": manager.id,
        "verified_at": datetime(2026, 8, 21, 11, 30, 0),
    }, update=False)

    _record(env, "sedar.hsse.corrective.action", "action_demo_verified_line_handling", {
        "name": "Refresh line-handling communication protocol",
        "incident_id": incident.id,
        "assigned_user_id": manager.id,
        "due_date": date(2026, 8, 21),
        "severity": "high",
        "critical_control": False,
        "description": "Review the line-handling briefing and confirm repeat-back protocol.",
        "completion_note": "Protocol was reviewed with the tug crew and dispatcher.",
        "state": "verified",
        "completed_by_id": manager.id,
        "completed_at": datetime(2026, 8, 21, 10, 30, 0),
        "verified_by_id": manager.id,
        "verified_at": datetime(2026, 8, 21, 11, 15, 0),
    }, update=False)

    inspection = _record(env, "sedar.hsse.inspection", "inspection_demo_overdue_finding", {
        "inspection_type": "vessel",
        "inspection_datetime": datetime(2026, 8, 15, 8, 0, 0),
        "inspector_id": manager.id,
        "service_order_id": service_order.id if service_order else False,
        "tugboat_id": tugboat.id if tugboat else False,
        "berth_id": berth.id if berth else False,
        "summary": "Demo vessel safety inspection before dispatch readiness review.",
        "state": "completed",
    }, update=False)

    if not inspection.finding_ids:
        overdue_due_date = date.today() - timedelta(days=3)
        finding = _record(env, "sedar.hsse.inspection.finding", "finding_demo_overdue_fire_extinguisher", {
            "inspection_id": inspection.id,
            "name": "Fire extinguisher inspection tag overdue",
            "severity": "critical",
            "assigned_user_id": manager.id,
            "due_date": overdue_due_date,
            "description": "Update fire extinguisher inspection tag and verify equipment is serviceable.",
            "state": "open",
        }, update=False)
        _record(env, "sedar.hsse.corrective.action", "action_demo_critical_fire_extinguisher", {
            "name": "Verify fire extinguisher readiness",
            "inspection_finding_id": finding.id,
            "assigned_user_id": manager.id,
            "due_date": overdue_due_date,
            "severity": "critical",
            "critical_control": True,
            "description": "Correct the overdue extinguisher inspection tag before operational release.",
            "state": "open",
        }, update=False)

    _record(env, "sedar.hsse.permit", "permit_demo_expired_required_hot_work", {
        "permit_type": "hot_work",
        "permit_number": "DEMO-HOT-2026-001",
        "issuing_authority": "Demo Port Safety Office",
        "valid_from": date(2026, 7, 1),
        "valid_until": date.today() - timedelta(days=1),
        "required_for_operations": True,
        "service_order_id": service_order.id if service_order else False,
        "tugboat_id": tugboat.id if tugboat else False,
        "berth_id": berth.id if berth else False,
        "note": "Demo expired required permit used to show an operational HSSE exception.",
    }, update=False)

    risk = _record(env, "sedar.hsse.risk.assessment", "risk_demo_berthing_line_handling", {
        "assessment_date": date(2026, 8, 18),
        "activity": "Berthing tug assist line handling",
        "hazard": "Snap-back zone exposure",
        "existing_controls": "Toolbox talk, exclusion zone, PPE, and tug master confirmation.",
        "additional_controls": "Repeat-back protocol and visible snap-back zone marking.",
        "likelihood": 3,
        "impact": 4,
        "owner_id": manager.id,
        "service_order_id": service_order.id if service_order else False,
        "tugboat_id": tugboat.id if tugboat else False,
        "berth_id": berth.id if berth else False,
        "state": "approved",
        "approved_by_id": manager.id,
        "approved_at": datetime(2026, 8, 18, 14, 0, 0),
    }, update=False)

    meeting = _record(env, "sedar.hsse.meeting", "meeting_demo_toolbox", {
        "meeting_type": "toolbox",
        "meeting_datetime": datetime(2026, 8, 20, 7, 30, 0),
        "facilitator_id": manager.id,
        "service_order_id": service_order.id if service_order else False,
        "operation_id": operation.id if operation else False,
        "tugboat_id": tugboat.id if tugboat else False,
        "berth_id": berth.id if berth else False,
        "attendee_employee_ids": [Command.set([employee.id])] if employee else [Command.clear()],
        "topic": "Line handling and snap-back zone awareness",
        "minutes": "Crew reviewed line handling hazards, exclusion zones, communication, and stop-work authority.",
    }, update=False)

    if employee:
        _record(env, "sedar.hsse.training.record", "training_demo_safety_orientation", {
            "course_name": "Marine Safety Orientation",
            "training_type": "orientation",
            "employee_id": employee.id,
            "crew_profile_id": crew_profile.id if crew_profile else False,
            "completion_date": date(2026, 8, 10),
            "expiry_date": date(2027, 8, 10),
            "readiness_applicable": True,
            "note": "Demo HSSE training evidence for the crew readiness story.",
        }, update=False)

from datetime import datetime

from odoo import Command


MODULE = "sedar_marine_maintenance"


def _record(env, model, xmlid, values):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid)
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
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
    tugs = {
        "atlas": env.ref("sedar_service_order_demo.tug_atlas", raise_if_not_found=False),
        "bantay": env.ref("sedar_service_order_demo.tug_bantay", raise_if_not_found=False),
        "harbor_one": env.ref("sedar_service_order_demo.tug_harbor_one", raise_if_not_found=False),
    }
    if not all(tugs.values()):
        return

    team = _record(env, "maintenance.team", "team_marine_technical", {
        "name": "Demo Marine Technical",
        "company_id": company.id,
    })
    category = _record(env, "maintenance.equipment.category", "category_tugboat_systems", {
        "name": "Demo Tugboat Systems",
    })

    equipment_specs = [
        ("atlas_main_engine", "STS Atlas Main Engine", "atlas", "propulsion", "critical"),
        ("atlas_radar", "STS Atlas Radar", "atlas", "navigation", "major"),
        ("bantay_main_engine", "STS Bantay Main Engine", "bantay", "propulsion", "critical"),
        ("harbor_one_generator", "STS Harbor One Generator", "harbor_one", "electrical", "major"),
    ]
    equipment = {}
    for xmlid, name, tug_key, system, criticality in equipment_specs:
        equipment[xmlid] = _record(env, "maintenance.equipment", xmlid, {
            "name": name,
            "category_id": category.id,
            "maintenance_team_id": team.id,
            "sedar_tugboat_id": tugs[tug_key].id,
            "sedar_system": system,
            "sedar_criticality": criticality,
            "sedar_installation_date": "2024-01-15",
            "sedar_running_interval_hours": 500,
        })

    _record(env, "maintenance.request", "work_order_atlas_planned", {
        "name": "Demo PMS - STS Atlas Main Engine 500-hour service",
        "maintenance_type": "preventive",
        "equipment_id": equipment["atlas_main_engine"].id,
        "maintenance_team_id": team.id,
        "schedule_date": datetime(2026, 8, 20, 9, 0, 0),
        "duration": 4,
        "priority": "1",
        "sedar_tugboat_id": tugs["atlas"].id,
        "sedar_work_order_type": "planned",
        "sedar_availability_impact": "advisory",
        "sedar_priority": "medium",
        "sedar_spare_part_note": "Oil filter set and engine oil reservation pending Inventory slice.",
    })
    _record(env, "maintenance.request", "work_order_bantay_defect", {
        "name": "Demo Defect - STS Bantay cooling-water leak",
        "maintenance_type": "corrective",
        "equipment_id": equipment["bantay_main_engine"].id,
        "maintenance_team_id": team.id,
        "schedule_date": datetime(2026, 8, 13, 7, 0, 0),
        "duration": 8,
        "priority": "3",
        "sedar_tugboat_id": tugs["bantay"].id,
        "sedar_work_order_type": "defect",
        "sedar_defect_source": "Tug Master report during pre-departure inspection.",
        "sedar_availability_impact": "blocking",
        "sedar_priority": "high",
        "sedar_spare_part_note": "Pump seal kit required; stock reservation pending Inventory slice.",
    })
    plan = _record(env, "sedar.drydock.plan", "drydock_bantay_2026", {
        "name": "Demo Dry Dock - STS Bantay 2026",
        "tugboat_id": tugs["bantay"].id,
        "planned_start": datetime(2026, 9, 1, 8, 0, 0),
        "planned_end": datetime(2026, 9, 21, 17, 0, 0),
        "yard_name": "Demo Batangas Ship Repair Yard",
        "state": "planned",
        "availability_impact": "blocking",
        "scope_summary": "Hull inspection, propulsion overhaul, paint renewal, and safety equipment checks.",
    })
    _record(env, "sedar.drydock.milestone", "drydock_bantay_arrival", {
        "plan_id": plan.id,
        "sequence": 10,
        "name": "Yard arrival and docking",
        "planned_date": datetime(2026, 9, 1, 8, 0, 0),
        "state": "pending",
    })
    _record(env, "sedar.drydock.milestone", "drydock_bantay_sea_trial", {
        "plan_id": plan.id,
        "sequence": 20,
        "name": "Sea trial and release inspection",
        "planned_date": datetime(2026, 9, 20, 8, 0, 0),
        "state": "pending",
    })
    tugs["bantay"]._sedar_sync_maintenance_availability()

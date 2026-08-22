from datetime import datetime

from odoo import Command


MODULE = "sedar_service_order_demo"


def _record(env, model, xmlid, values):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid)
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            record.with_context(
                sedar_demo_reconcile=True,
                sedar_tariff_supersede=True,
                sedar_automated_dispatch=True,
            ).write(values)
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


def _ensure_people_foundation(env, company):
    department = _record(env, "hr.department", "department_operations", {
        "name": "Demo Marine Operations", "company_id": company.id,
    })
    job_names = {
        "MASTER": "Tug Master", "CHENG": "Chief Engineer", "DECK": "Deckhand",
        "OILER": "Oiler / Motorman", "CRO": "Customer Relations Officer",
        "CREWING": "Crewing and Operations Officer",
    }
    jobs = {
        code: _record(env, "hr.job", f"job_{code.lower()}", {
            "name": f"Demo {name}", "department_id": department.id,
        }) for code, name in job_names.items()
    }
    ranks = {
        code: _record(env, "sedar.crew.rank", f"rank_{code.lower()}", {
            "code": code, "name": job_names[code], "sequence": sequence * 10,
        })
        for sequence, code in enumerate(["MASTER", "CHENG", "OILER", "DECK"], start=1)
    }
    certificate_names = {
        "STCW": "STCW Basic Safety Training",
        "SIRB": "Seafarer's Identification and Record Book",
        "MED": "Seafarer Medical Certificate",
        "DAT": "Drug and Alcohol Test Clearance",
        "COC-M": "Master Certificate of Competency",
        "COC-E": "Engineer Certificate of Competency",
    }
    certificate_types = {
        code: _record(env, "sedar.crew.certificate.type", f"certificate_type_{code.lower().replace('-', '_')}", {
            "code": code, "name": name,
        }) for code, name in certificate_names.items()
    }
    return department, jobs, ranks, certificate_types


def _ensure_clients_and_vessels(env, company, services, port, base):
    client_specs = [
        ("archipelago", "Archipelago Cargo Lines, Inc."),
        ("baylink", "BayLink Shipping Corporation"),
        ("pacific", "Pacific Meridian Tankers, Inc."),
        ("island", "Island Gateway Logistics Corporation"),
    ]
    clients = []
    for index, (code, name) in enumerate(client_specs, start=1):
        client = _record(env, "res.partner", f"client_{code}", {
            "name": name, "is_company": True, "company_type": "company",
            "email": f"operations@{code}.example.com", "phone": f"+63 2 8800 10{index:02d}",
            "street": f"Demo Office {index}, Port Area", "city": "Batangas City",
            "country_id": env.ref("base.ph").id,
        })
        clients.append(client)
        for contact_number, role in enumerate(["Operations", "Billing"], start=1):
            _record(env, "res.partner", f"contact_{code}_{contact_number}", {
                "name": f"Demo {role} Contact {index}", "parent_id": client.id,
                "email": f"contact{contact_number}@{code}.example.com",
                "phone": f"+63 917 555 {index}{contact_number}00",
            })
    portal_partner = _record(env, "res.partner", "partner_client_portal", {
        "name": "Demo Client Portal User", "parent_id": clients[0].id,
        "email": "client@sedar.demo",
    })
    _record(env, "res.users", "user_client_portal", {
        "name": "Demo Client Portal User", "login": "client@sedar.demo",
        "password": "clientdemo", "partner_id": portal_partner.id,
        "company_id": company.id, "company_ids": [Command.set([company.id])],
        "group_ids": [Command.set([env.ref("base.group_portal").id])],
    })
    vessel_specs = [
        ("mv_luzon_star", "MV Luzon Star", 0, "cargo", "9876101", 18200),
        ("mv_visayas_trader", "MV Visayas Trader", 0, "cargo", "9876102", 12400),
        ("mt_bay_spirit", "MT Bay Spirit", 1, "tanker", "9876103", 28600),
        ("mv_pacific_meridian", "MV Pacific Meridian", 2, "cargo", "9876104", 22100),
        ("mt_sampaguita", "MT Sampaguita", 2, "tanker", "9876105", 31400),
        ("barge_gateway_7", "Barge Gateway 7", 3, "barge", "9876106", 8500),
    ]
    vessels = {
        xmlid: _record(env, "sedar.client.vessel", xmlid, {
            "name": name, "owner_id": clients[owner].id, "vessel_type": vessel_type,
            "imo_number": imo, "call_sign": f"DU{imo[-4:]}", "gross_tonnage": tonnage,
            "length_overall": 145 + owner * 12, "draft": 7.5 + owner,
        }) for xmlid, name, owner, vessel_type, imo, tonnage in vessel_specs
    }
    for index, (code, _) in enumerate(client_specs):
        for service, rate, basis in [
            ("harbor", 4800, "per_tug_hour"), ("towage", 6500, "per_tug_hour"),
            ("berthing", 18000, "per_service"), ("shifting", 22000, "per_service"),
        ]:
            _record(env, "sedar.client.tariff", f"tariff_{code}_{service}", {
                "partner_id": clients[index].id, "service_type_id": services[service].id,
                "port_id": port.id, "terminal_id": base.id, "pricing_basis": basis,
                "rate": rate + index * 450, "minimum_charge": 12000,
                "currency_id": company.currency_id.id, "valid_from": "2026-01-01",
                "valid_until": "2026-12-31", "approved": True,
                "approval_state": "approved", "approval_reference": "DEMO-PRESIDENT-AUTHORIZATION",
            })
    return clients, vessels


def _ensure_tugs_and_crew(env, company, port, standard, high_power, department, jobs,
                          ranks, certificate_types):
    tug_specs = [
        ("atlas", "STS Atlas", high_power, 50, "available"),
        ("harbor_one", "STS Harbor One", standard, 35, "available"),
        ("matikas", "STS Matikas", standard, 40, "assigned"),
        ("bantay", "STS Bantay", standard, 30, "maintenance"),
        ("lakas", "STS Lakas", standard, 45, "available"),
    ]
    tugs = {
        code: _record(env, "sedar.tugboat", f"tug_{code}", {
            "name": name, "registration_number": f"SEDAR-TUG-{index:03d}",
            "call_sign": f"DUA{index:02d}", "mmsi": f"5489000{index:02d}",
            "tug_class_id": tug_class.id, "bollard_pull": pull,
            "fuel_capacity": 60000 + index * 5000, "home_port_id": port.id,
            "availability_status": availability,
        })
        for index, (code, name, tug_class, pull, availability)
        in enumerate(tug_specs, start=1)
    }
    crew_names = {
        "MASTER": ["Ramon Alvarado", "Joel Bautista", "Nestor Cruz", "Mario Dela Pena", "Victor Enriquez"],
        "CHENG": ["Edgar Flores", "Samuel Garcia", "Rolando Herrera", "Dennis Ignacio", "Arturo Javier"],
        "DECK": ["Paolo Lim", "Kevin Mendoza", "Noel Navarro", "Oscar Ong", "Benito Pascual", "Rico Quinto", "Leo Ramos", "Tony Santos", "Ulysses Tan"],
        "OILER": ["Warren Uy", "Xavier Valencia", "Yuri Villanueva"],
    }
    profiles = {code: [] for code in crew_names}
    employee_number = 1
    home_tugs = list(tugs.values())
    for rank_code, names in crew_names.items():
        for rank_index, name in enumerate(names):
            employee = _record(env, "hr.employee", f"employee_{employee_number:03d}", {
                "name": name, "department_id": department.id, "job_id": jobs[rank_code].id,
                "work_email": f"crew{employee_number:03d}@sedar-demo.example.com",
                "company_id": company.id,
            })
            if rank_code == "MASTER":
                user = _record(env, "res.users", f"user_tug_master_{rank_index + 1}", {
                    "name": name, "login": f"tugmaster{rank_index + 1}@sedar.demo",
                    "password": "tugdemo", "company_id": company.id,
                    "company_ids": [Command.set([company.id])],
                    "group_ids": [Command.set([
                        env.ref("base.group_user").id,
                        env.ref("sedar_marine_operations.group_tug_master").id,
                    ])],
                })
                employee.user_id = user.id
            profile = _record(env, "sedar.crew.profile", f"crew_{employee_number:03d}", {
                "employee_id": employee.id, "employee_number": f"SEDAR-DEMO-{employee_number:03d}",
                "rank_id": ranks[rank_code].id,
                "home_tugboat_id": home_tugs[rank_index % len(home_tugs)].id,
                "seafarer_number": f"SRB-DEMO-{employee_number:05d}",
                "availability_status": "leave" if employee_number == 22 else "available",
            })
            profiles[rank_code].append(profile)
            _ensure_crew_certificates(env, profile, rank_code, employee_number, certificate_types)
            employee_number += 1
    _ensure_support_people(env, company, department, jobs)
    return tugs, profiles


def _ensure_crew_certificates(env, profile, rank_code, employee_number, certificate_types):
    certificate_codes = ["STCW", "SIRB", "MED", "DAT"]
    if rank_code == "MASTER":
        certificate_codes.append("COC-M")
    if rank_code == "CHENG":
        certificate_codes.append("COC-E")
    for certificate_code in certificate_codes:
        if employee_number == 21 and certificate_code == "MED":
            continue
        expiry = "2027-08-31"
        if employee_number == 10 and certificate_code == "MED":
            expiry = "2026-07-31"
        if employee_number == 20 and certificate_code == "STCW":
            expiry = "2026-08-20"
        _record(env, "sedar.crew.certificate", f"crew_{employee_number:03d}_{certificate_code.lower().replace('-', '_')}", {
            "crew_profile_id": profile.id,
            "certificate_type_id": certificate_types[certificate_code].id,
            "certificate_number": f"{certificate_code}-DEMO-{employee_number:03d}",
            "issue_date": "2025-01-15", "expiry_date": expiry,
        })


def _ensure_support_people(env, company, department, jobs):
    for xmlid, name, job_code in [
        ("employee_cro", "Carina Reyes", "CRO"),
        ("employee_crewing_officer", "Miguel Torres", "CREWING"),
    ]:
        _record(env, "hr.employee", xmlid, {
            "name": name, "department_id": department.id, "job_id": jobs[job_code].id,
            "work_email": f"{xmlid[9:]}@sedar-demo.example.com", "company_id": company.id,
        })
    for xmlid, name, login, password, group in [
        ("user_billing_officer", "Demo Billing Officer", "billing@sedar.demo", "billingdemo",
         "sedar_marine_finance.group_billing_officer"),
        ("user_accounting_manager", "Demo Accounting Manager", "accounting@sedar.demo",
         "accountingdemo", "sedar_marine_finance.group_accounting_manager"),
    ]:
        _record(env, "res.users", xmlid, {
            "name": name, "login": login, "password": password, "company_id": company.id,
            "company_ids": [Command.set([company.id])],
            "group_ids": [Command.set([env.ref(group).id])],
        })


def _ensure_assignments(env, orders, order_services, tugs, templates, profiles):
    assignment_specs = [
        ("ready", "ready", "atlas", {"MASTER": [0], "CHENG": [0], "DECK": [0, 1]}),
        ("missing_engineer", "missing_engineer", "lakas", {"MASTER": [1], "OILER": [0], "DECK": [2, 3, 4]}),
        ("expired_medical", "expired_medical", "harbor_one", {"MASTER": [2], "CHENG": [4], "DECK": [5, 6]}),
        ("maintenance_tug", "maintenance_tug", "bantay", {"MASTER": [3], "CHENG": [2], "DECK": [7, 8]}),
        ("completed", "completed", "matikas", {"MASTER": [4], "CHENG": [3], "DECK": [2, 3]}),
        ("two_tug_a", "two_tug", "atlas", {"MASTER": [0], "CHENG": [0], "OILER": [1], "DECK": [0, 1, 2]}),
        ("two_tug_b", "two_tug", "harbor_one", {"MASTER": [1], "CHENG": [1], "OILER": [2], "DECK": [3, 4, 5]}),
    ]
    for assignment_code, order_code, tug_code, crew_map in assignment_specs:
        order = orders[order_code]
        assignment = _record(env, "sedar.tug.assignment", f"assignment_{assignment_code}", {
            "order_id": order.id, "tugboat_id": tugs[tug_code].id,
            "state": "confirmed" if order.state == "completed" else "planned",
        })
        for line in templates[order_services[order_code]].line_ids:
            rank_code = line.rank_id.code
            requirement = _record(env, "sedar.manning.requirement", f"requirement_{assignment_code}_{rank_code.lower()}", {
                "tug_assignment_id": assignment.id, "rank_id": line.rank_id.id,
                "required_count": line.required_count,
                "required_certificate_type_ids": [Command.set(line.required_certificate_type_ids.ids)],
            })
            selected = crew_map.get(rank_code, [])
            for position, profile_index in enumerate(selected, start=1):
                _record(env, "sedar.crew.assignment", f"crew_assignment_{assignment_code}_{rank_code.lower()}_{position}", {
                    "requirement_id": requirement.id,
                    "crew_profile_id": profiles[rank_code][profile_index].id,
                    "state": "confirmed" if order.state == "completed" else "planned",
                })
            if len(selected) < line.required_count:
                _record(env, "sedar.crew.shortage", f"shortage_{assignment_code}_{rank_code.lower()}", {
                    "requirement_id": requirement.id,
                    "missing_count": line.required_count - len(selected),
                    "reason": "no_qualified", "notes": "Intentional service-order demo shortage.",
                })
        if order.state == "completed":
            master_profile = profiles["MASTER"][crew_map["MASTER"][0]]
            duration = 6 if order_services[order_code] == "towage" else 3
            completion_at = order.requested_start.replace(hour=order.requested_start.hour + duration)
            assignment.with_context(sedar_completion_action=True).write({
                "actual_start": order.requested_start, "actual_end": completion_at,
                "completion_note": "Demo Tug Master completion declaration.",
                "completion_state": "submitted",
                "completion_declared_by_id": master_profile.employee_id.user_id.id,
                "completion_declared_at": completion_at,
            })
    expired_requirement = env.ref(f"{MODULE}.requirement_expired_medical_cheng")
    _record(env, "sedar.crew.shortage", "shortage_expired_medical", {
        "requirement_id": expired_requirement.id, "missing_count": 1,
        "reason": "certificate",
        "notes": "Assigned Chief Engineer has an expired medical certificate.",
    })


def post_init_hook(env):
    company = env.company
    company.sedar_configure_demo_currency()
    port = env.ref("sedar_marine_operations.port_batangas")
    base = env.ref("sedar_marine_operations.berth_batangas_base")
    anchorage = env.ref("sedar_marine_operations.berth_batangas_anchorage")
    standard = env.ref("sedar_marine_operations.tug_class_standard")
    high_power = env.ref("sedar_marine_operations.tug_class_high_power")
    services = {
        key: env.ref(f"sedar_marine_operations.service_type_{key}")
        for key in ["harbor", "berthing", "towage", "shifting", "emergency"]
    }

    department, jobs, ranks, certificate_types = _ensure_people_foundation(env, company)
    clients, vessels = _ensure_clients_and_vessels(env, company, services, port, base)

    tugs, profiles = _ensure_tugs_and_crew(
        env, company, port, standard, high_power, department, jobs, ranks, certificate_types
    )

    template_specs = {
        "harbor": [("MASTER", 1), ("CHENG", 1), ("DECK", 2)],
        "berthing": [("MASTER", 1), ("CHENG", 1), ("DECK", 2)],
        "shifting": [("MASTER", 1), ("CHENG", 1), ("DECK", 2)],
        "towage": [("MASTER", 1), ("CHENG", 1), ("OILER", 1), ("DECK", 3)],
        "emergency": [("MASTER", 1), ("CHENG", 1), ("DECK", 3)],
    }
    templates = {}
    common_certificates = [certificate_types[code].id for code in ["STCW", "SIRB", "MED", "DAT"]]
    for service, lines in template_specs.items():
        templates[service] = _record(env, "sedar.manning.template", f"template_{service}", {
            "name": f"Demo {services[service].name} Manning", "service_type_id": services[service].id,
        })
        for sequence, (rank_code, count) in enumerate(lines, start=1):
            required = list(common_certificates)
            if rank_code == "MASTER": required.append(certificate_types["COC-M"].id)
            if rank_code == "CHENG": required.append(certificate_types["COC-E"].id)
            _record(env, "sedar.manning.template.line", f"template_{service}_{rank_code.lower()}", {
                "template_id": templates[service].id, "sequence": sequence * 10,
                "rank_id": ranks[rank_code].id, "required_count": count,
                "required_certificate_type_ids": [Command.set(required)],
            })

    order_specs = [
        ("draft", 0, "mv_luzon_star", "harbor", 5, "draft", 1, standard),
        ("portal_submitted", 1, "mt_bay_spirit", "berthing", 6, "submitted", 1, standard),
        ("tariff_resolved", 2, "mv_pacific_meridian", "towage", 7, "quoted", 1, high_power),
        ("pricing_review", 3, "barge_gateway_7", "emergency", 7, "review", 1, standard),
        ("no_tug", 0, "mv_visayas_trader", "harbor", 8, "planning", 1, standard),
        ("ready", 1, "mt_bay_spirit", "harbor", 10, "planning", 1, high_power),
        ("missing_engineer", 2, "mt_sampaguita", "towage", 11, "blocked", 1, standard),
        ("expired_medical", 3, "barge_gateway_7", "berthing", 12, "blocked", 1, standard),
        ("maintenance_tug", 0, "mv_luzon_star", "shifting", 13, "blocked", 1, standard),
        ("completed", 2, "mv_pacific_meridian", "harbor", 3, "completed", 1, standard),
        ("two_tug", 0, "mv_visayas_trader", "towage", 14, "completed", 2, high_power),
    ]
    orders = {}
    order_services = {}
    for code, client_index, vessel_key, service, day, state, tug_count, tug_class in order_specs:
        client, vessel = clients[client_index], vessels[vessel_key]
        contact = env["res.partner"].search([("parent_id", "=", client.id)], limit=1)
        orders[code] = _record(env, "sedar.marine.service.order", f"order_{code}", {
            "client_id": client.id, "contact_id": contact.id,
            "request_channel": "portal" if code == "portal_submitted" else "internal",
            "client_reference": f"DEMO-{code.upper().replace('_', '-')}",
            "priority": "emergency" if service == "emergency" else "normal",
            "assisted_vessel_id": vessel.id, "assisted_vessel_name": vessel.name,
            "service_type_id": services[service].id, "number_of_tugs": tug_count,
            "tug_class_id": tug_class.id, "required_bollard_pull": tug_class.minimum_bollard_pull,
            "scope_of_work": f"Demonstration {services[service].name.lower()} service.",
            "port_id": port.id, "terminal_id": base.id, "origin_berth_id": anchorage.id,
            "destination_berth_id": base.id, "requested_start": _dt(day),
            "estimated_duration_hours": 6 if service == "towage" else 3,
            "state": state,
        })
        order_services[code] = service

    for order in orders.values():
        if order.state in {"quoted", "confirmed", "planning", "blocked", "ready", "dispatched", "in_progress", "completed"}:
            order._freeze_pricing()

    _ensure_assignments(env, orders, order_services, tugs, templates, profiles)

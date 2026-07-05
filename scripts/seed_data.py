"""Idempotent SEDAR demo-data seeder. Run inside the Odoo container shell.

Usage:
    docker compose exec -T odoo odoo shell -d sedar < scripts/seed_data.py
"""


def seed(env):
    Partner = env['res.partner']
    Vessel = env['sedar.vessel']
    JobOrder = env['sedar.job.order']
    VoyageLog = env['sedar.voyage.log']
    FuelLog = env['sedar.fuel.log']
    TowageBilling = env['sedar.towage.billing']
    Incident = env['sedar.hsse.incident']
    NearMiss = env['sedar.hsse.near.miss']
    Inspection = env['sedar.hsse.inspection']
    Risk = env['sedar.hsse.risk.assessment']
    Permit = env['sedar.hsse.permit']
    Employee = env['hr.employee']
    Crew = env['sedar.crew.member']
    Rotation = env['sedar.crew.rotation']
    Cert = env['sedar.crew.certification']
    Medical = env['sedar.crew.medical']
    Leave = env['sedar.crew.leave']
    Contract = env['sedar.doc.contract']
    VesselCert = env['sedar.doc.vessel.cert']
    Insurance = env['sedar.doc.insurance']
    DocRecord = env['sedar.doc.record']
    Equipment = env['maintenance.equipment']

    if Vessel.search_count([]):
        ensure_native_demo(env)
        env.cr.commit()
        print('Seed data already present; native demo data checked.')
        return

    company = env.company
    php = env.ref('base.PHP', raise_if_not_found=False)
    if php:
        company.currency_id = php

    vessels = Vessel.create([
        {
            'name': 'SEDAR Kalinga',
            'registry_no': 'IMO-9123456',
            'vessel_type': 'tug',
            'capacity': 3200.0,
            'status': 'active',
        },
        {
            'name': 'SEDAR Bantay',
            'registry_no': 'IMO-9123457',
            'vessel_type': 'tug',
            'capacity': 2800.0,
            'status': 'active',
        },
        {
            'name': 'SEDAR Tagumpay',
            'registry_no': 'IMO-9123458',
            'vessel_type': 'barge',
            'capacity': 5000.0,
            'status': 'dry_dock',
        },
    ])

    customers = Partner.create([
        {'name': 'Manila South Harbor Terminal'},
        {'name': 'Batangas International Port Corp'},
    ])

    job1 = JobOrder.create({
        'customer_id': customers[0].id,
        'vessel_id': vessels[0].id,
        'origin_port': 'Manila South Harbor',
        'destination_port': 'Manila North Harbor',
        'state': 'completed',
    })
    JobOrder.create({
        'customer_id': customers[1].id,
        'vessel_id': vessels[1].id,
        'origin_port': 'Batangas Port',
        'destination_port': 'Subic Bay',
        'state': 'in_progress',
    })
    JobOrder.create({
        'customer_id': customers[0].id,
        'vessel_id': vessels[0].id,
        'origin_port': 'Manila South Harbor',
        'destination_port': 'Corregidor',
        'state': 'requested',
    })

    VoyageLog.create({
        'job_order_id': job1.id,
        'distance_nm': 12.4,
        'weather_notes': 'Clear skies, calm seas',
    })
    FuelLog.create([
        {'vessel_id': vessels[0].id, 'liters': 850.0, 'cost': 62000.0},
        {'vessel_id': vessels[1].id, 'liters': 620.0, 'cost': 45000.0},
    ])
    bill = TowageBilling.create({
        'job_order_id': job1.id,
        'rate_basis': 'job',
        'rate': 45000.0,
    })
    bill.action_create_invoice()

    Incident.create({
        'severity': 'medium',
        'vessel_id': vessels[1].id,
        'location': 'Batangas Port',
        'description': 'Mooring line snapped during berthing',
        'corrective_action': 'Replaced line, briefed crew on load limits',
    })
    NearMiss.create({
        'description': 'Crew member nearly slipped on wet deck',
        'risk_category': 'personnel',
    })
    Inspection.create({
        'inspection_type': 'vessel',
        'line_ids': [
            (0, 0, {'item': 'Fire extinguishers charged', 'result': 'pass'}),
            (0, 0, {'item': 'Life jackets count', 'result': 'fail', 'remarks': '2 missing'}),
        ],
    })
    Risk.create({
        'activity': 'Towing in heavy weather',
        'hazard': 'Line parting under load',
        'likelihood': '3',
        'severity': '4',
        'mitigation': 'Use higher-rated tow line and enforce exclusion zones.',
    })
    Permit.create({
        'name': 'Certificate of Vessel Safety',
        'permit_type': 'Safety',
        'issuing_authority': 'marina',
        'expiry_date': '2026-12-31',
    })

    employees = Employee.create([
        {'name': 'Juan Dela Cruz'},
        {'name': 'Pedro Reyes'},
    ])
    crew = Crew.create([
        {'employee_id': employees[0].id, 'rank': 'Master', 'vessel_id': vessels[0].id},
        {'employee_id': employees[1].id, 'rank': 'Chief Engineer', 'vessel_id': vessels[1].id},
    ])
    Rotation.create({
        'crew_id': crew[0].id,
        'vessel_id': vessels[0].id,
        'onboard_date': '2026-07-01',
        'state': 'onboard',
    })
    Cert.create({
        'crew_id': crew[0].id,
        'cert_type': 'STCW Basic Safety Training',
        'expiry_date': '2027-01-01',
    })
    Medical.create({'crew_id': crew[1].id, 'fit_for_duty': True, 'expiry_date': '2026-09-01'})
    Leave.create({
        'crew_id': crew[1].id,
        'date_from': '2026-08-01',
        'date_to': '2026-08-10',
        'state': 'submitted',
    })

    Contract.create({
        'name': 'Fuel Supply Agreement 2026',
        'partner_id': customers[0].id,
        'contract_type': 'Supply',
        'expiry_date': '2027-06-30',
    })
    VesselCert.create({
        'vessel_id': vessels[0].id,
        'cert_type': 'Certificate of Vessel Registry',
        'issuing_body': 'MARINA',
        'expiry_date': '2027-03-15',
    })
    Insurance.create({
        'policy_no': 'MARINE-2026-0042',
        'insurer': 'Malayan Insurance',
        'coverage_type': 'Hull and Machinery',
        'expiry_date': '2026-08-01',
    })
    DocRecord.create({
        'name': 'Board Resolution No. 2026-05',
        'category': 'board_resolution',
        'reference_no': 'BR-2026-05',
    })

    Equipment.create({'name': 'Main Engine - Port', 'vessel_id': vessels[0].id})
    ensure_native_demo(env)

    env.cr.commit()
    print('Seed data loaded successfully.')


def ensure_native_demo(env):
    Partner = env['res.partner']
    Product = env['product.product']
    PurchaseOrder = env['purchase.order']
    Employee = env['hr.employee']
    Job = env['hr.job']
    Applicant = env['hr.applicant']
    Dashboard = env['sedar.dashboard']

    vendor = Partner.search([('name', '=', 'Cebu Marine Supplies')], limit=1)
    if not vendor:
        vendor = Partner.create({'name': 'Cebu Marine Supplies', 'supplier_rank': 1})

    product = Product.search([('name', '=', 'Marine Diesel Oil - MDO')], limit=1)
    if not product:
        product = Product.create({
            'name': 'Marine Diesel Oil - MDO',
            'list_price': 72.50,
            'standard_price': 68.00,
            'sale_ok': False,
            'purchase_ok': True,
        })

    if not PurchaseOrder.search([('partner_id', '=', vendor.id)], limit=1):
        PurchaseOrder.create({
            'partner_id': vendor.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': 5000.0,
                'product_uom': product.uom_po_id.id,
                'price_unit': 68.00,
                'date_planned': '2026-07-15 08:00:00',
            })],
        })

    if not Employee.search([('name', '=', 'Maria Santos')], limit=1):
        Employee.create({'name': 'Maria Santos', 'job_title': 'Operations Coordinator'})

    job = Job.search([('name', '=', 'Able Seaman')], limit=1)
    if not job:
        job = Job.create({'name': 'Able Seaman'})

    if not Applicant.search([('partner_name', '=', 'Ramon Cruz')], limit=1):
        Applicant.create({
            'name': 'Able Seaman Application - Ramon Cruz',
            'partner_name': 'Ramon Cruz',
            'email_from': 'ramon.cruz@example.com',
            'job_id': job.id,
        })

    if not Dashboard.search([], limit=1):
        Dashboard.create({})


seed(env)  # noqa: F821 -- env is injected by odoo shell

# SEDAR Odoo 19 Development Workspace

This workspace is prepared for an Odoo 19.0 development environment.

## Layout

- `config/` - Odoo configuration
- `custom-addons/` - SEDAR custom modules
- `data/` - local PostgreSQL and Odoo data mounts
- `docker-compose.yml` - Odoo 19 and PostgreSQL services

## Start

Docker Desktop must be running before starting the stack.

```powershell
docker compose up -d
```

Then open http://localhost:8069.

The default development database credentials are defined in `docker-compose.yml` and
`config/odoo.conf`. Change them before using this outside a local development machine.

## Document Intake Workflow

Every SEDAR source form follows this sequence:

1. **Extract content completely** - inspect the supplied PDF or image and transcribe every visible item, including metadata, fields, instructions, statements, confidentiality notices, checkbox options, table labels, signature labels, and closing text. Do not summarize or omit content. Mark genuinely unreadable text as `[unclear]` for confirmation.
2. **Wait for approval** - present the extraction for business-owner confirmation.
3. **Add planning catalogue** - record the approved definition under `documents/`.
4. **Add to Odoo Documents module** - add the metadata, field definition, and approved source file to `sedar_document_control`.

The first two approved entries are ADM-2 and ADM-3. The custom addon creates the SEDAR menu,
Document Catalogue, Typed Template Fields, Controlled Documents, and Employee Document Requests.
It loads the approved source PDFs and typed field templates when installed.

## Fillable Document Workflow

1. Open **SEDAR > Document Control > Employee Document Requests**.
2. Create a request and select a document template such as ADM-5.
3. Enter the applicant or employee and assigned HR user.
4. Open the **Fillable Form** tab. The request generates the template's typed fields automatically.
5. Enter text, dates, whole numbers, decimal numbers, selections, Yes/No answers, signatures, and uploaded attachments in their corresponding controls.
6. Use **Submit**. Odoo blocks submission when a required field is incomplete.
7. HR reviews and approves or rejects the request.

The template's **Typed Template Fields** menu shows each field's expected data type. The original
PDF remains available under **Controlled Documents** as the source/reference copy.

After Docker Desktop is running, initialize the demo database and install the addon:

```powershell
docker compose up -d
docker compose exec odoo odoo -d sedar_demo -i base,sedar_document_control --without-demo=all --stop-after-init
docker compose restart odoo
```

Then open `http://localhost:8069` and select the `sedar_demo` database.

## Marine Service Orders

The `sedar_marine_operations` addon is intentionally limited to service-order intake and the
client dashboard. Its supporting master data includes service types, ports/locations, client
vessels, tug classes, and client tariffs because these are required to provide normalized
dropdowns and server-side pricing.

Internal users open **SEDAR > Marine Operations > Service Order Dashboard** to create and review
orders. Tariffs and normalized vessel/location lists are managed under the same Marine Operations
menu.

Clients open `http://localhost:8069/my`, choose **Marine Service Orders**, and use
**New Service Order**. A client can only see orders belonging to their commercial account.

Local demo portal credentials:

- Login: `client@sedar.demo`
- Password: `clientdemo`

The local demo database contains a sample Batangas tariff for `SEDAR Demo Shipping Client`.
These credentials and rates are local database fixtures and are not production configuration.

## Service Order Seed Data

The optional `sedar_service_order_demo` addon contains fictional records only. It seeds the
service-order scope with four clients, six assisted vessels, five tugboats, 24 employees,
22 marine crew profiles, certificates, manning templates, tariffs, and eleven service orders.
It deliberately includes ready, no-tug, missing-crew, expired-medical, maintenance-hold,
pricing-review, completed, and two-tug scenarios.

Install or refresh the operational module and seed data with:

```powershell
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d sedar_demo `
  -u sedar_marine_operations -i sedar_service_order_demo --stop-after-init
docker compose restart odoo
```

Open **SEDAR > Marine Operations > Service Order Dashboard** to compare readiness states.
Use **Tugboats**, **Crew Profiles**, and **Tug and Crew Plans** to inspect the records behind
each result. The demo addon is separate so its fictional records can be removed independently
from the production-oriented operational models.

## Dispatch and Service Execution

The optional `sedar_marine_dispatch` addon extends a ready service order into an executable
marine operation. It records the dispatch-time tug and crew manifest, dispatch and start times,
per-tug movement milestones, activity logs, delays, completion evidence, actual duration, and
the billing-ready handoff. It does not create invoices, payroll entries, maintenance work orders,
or recruitment records.

Install the dispatch module after the service-order modules with:

```powershell
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d sedar_demo `
  -i sedar_marine_dispatch --stop-after-init
docker compose restart odoo
```

The separate `sedar_marine_dispatch_demo` addon creates a ready-to-dispatch operation and a
completed billing-ready operation with client-visible activity logs and a resolved port delay.

## Manpower Planning

The optional `sedar_manpower_planning` addon reviews operational crew shortages and separates
temporary or compliance issues from genuine headcount demand. It adds the Shortage Review Queue,
resolution actions, manpower requests, approval workflow, and internal job vacancies. It does
not publish Careers listings, create applicants, or create employees.

Install the manpower-planning module after dispatch with:

```powershell
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d sedar_demo `
  -i sedar_manpower_planning --stop-after-init
docker compose restart odoo
```

The separate `sedar_manpower_planning_demo` addon demonstrates three outcomes: a Chief Engineer
shortage becomes an approved internal vacancy, an expired medical creates a certification action,
and an employee-on-leave shortage creates a temporary replacement action. The vacancy remains
internal until a future HR/Careers slice explicitly approves publication.

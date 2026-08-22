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

After Docker Desktop is running, start the stack:

```powershell
docker compose up -d
```

Docker automatically creates the `sedar_demo` database, installs the complete SEDAR module stack,
loads the fictional seed data, and upgrades the custom modules on later starts. Then open
`http://localhost:8069/web?db=sedar_demo`. No manual Apps installation is required.

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

The operational, finance, document-control, and seed-data modules are installed and upgraded by
`docker compose up -d`.

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

## Marine Finance Demo

The custom model and field contract for this workflow is documented in
[`docs/custom-models.md`](../docs/custom-models.md).

The `sedar_marine_finance` addon adds the post-service billing workflow on top of Odoo
Accounting. Tug Masters declare actual completion per assigned tug. A Service Order enters
Billing Review only after every active tug is complete. Finance then reviews the frozen client
tariff, actual tug-hours, minimum charge, and explained adjustments before creating a draft
customer invoice.

Demo users:

- Tug Masters: `tugmaster1@sedar.demo` through `tugmaster5@sedar.demo`, password `tugdemo`
- Billing Officer: `billing@sedar.demo`, password `billingdemo`
- Accounting Manager: `accounting@sedar.demo`, password `accountingdemo`

The seeded two-tug towage order is completed by both Tug Masters and appears in
**SEDAR > Marine Finance > Billing Reviews**. It uses 12 actual tug-hours and an approved,
terminal-specific mock tariff. The Billing Officer can complete review and create the draft
invoice. The Accounting Manager can post it and register payment using standard Odoo Accounting.

## Recruitment Demo Baseline

The `sedar_recruitment_demo` addon is a non-production fixture module for Slice 1. It runs an
idempotent bootstrap on install and upgrade so a clean Docker database and a reused local
database both receive the same named fictional recruitment scenarios without creating duplicates.

The seeded recruitment scenarios include:

- New application awaiting HR review
- Qualified applicant awaiting interview scheduling
- Scheduled interview awaiting applicant confirmation
- Interview with reschedule requested
- Completed interview awaiting internal HR controls
- ADM-4A Background Inquiry and CM-053 Company Orientation controls
- Issued employment offer awaiting applicant response
- Applicant with pending ADM-5 requirements
- Applicant with verified ADM-5 requirements
- Rejected applicant
- Withdrawn applicant
- Successful applicant converted to an employee

The scenarios are linked to the existing Chief Engineer vacancy from the manpower demo, which in
turn traces back to the permanent headcount shortage in the Service Order demo. The manpower demo
also preserves non-hiring shortage examples for expired medical and leave/temporary reliever
handling.

Recruitment demo users:

- HR Recruiter: `hr@sedar.demo`, password `recruitdemo`
- HR Manager: `hrmanager@sedar.demo`, password `recruitdemo`
- Technical Interviewer: `interviewer@sedar.demo`, password `recruitdemo`
- Applicant portal user: `applicant@sedar.demo`, password `applicantdemo`

Open **SEDAR Recruitment > Applicant Processing** to review the internal HR scenarios. Open
`http://localhost:8069/my/sedar` as the applicant portal user to inspect the applicant-side
tracking scenario with a pending ADM-5 request.

For the Slice 3 HR-control demo, open the completed-interview applicant, then use **Create HR
Controls** to generate ADM-4A and CM-053 requests. HR completes, submits, reviews, and approves
those internal requests before **Request Requirements** can create the applicant-visible ADM-5
request. The applicant portal shows only the public progress status, not the confidential
background inquiry details.

For the Slice 4 offer demo, open **SEDAR Recruitment > Hiring Decisions and Offers** or the
applicant's **Offers** tab. HR issues an offer only after the internal controls are approved. The
applicant portal shows the issued offer summary and lets the applicant accept or decline it. An
accepted offer is required before HR can request ADM-5 or create the employee profile.

Run the Finance workflow tests through the isolated test runner:

```sh
python3 scripts/run_odoo_tests.py --module sedar_marine_finance
```

These accounts, tariffs, completions, and prices are fictional demo fixtures. Replace them with
approved SEDAR data and change all passwords before any non-local use.

## Local Quality Checks

Install the pinned developer tool from `sedar-new` without changing the Odoo image:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Check every Python function in the active Odoo 19 addons against the repository's complexity,
branch, and statement limits:

```sh
.venv/bin/ruff check custom-addons scripts
```

Run the isolated-runner safety tests after changing the runner itself:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

Run all SEDAR Python tests in a newly created, uniquely named database:

```sh
python3 scripts/run_odoo_tests.py
```

Run one module, or narrow that module to an Odoo class or method:

```sh
python3 scripts/run_odoo_tests.py --module sedar_marine_finance
python3 scripts/run_odoo_tests.py --module sedar_marine_finance \
  --test-tags /sedar_marine_finance:TestMarineFinanceWorkflow.test_missing_tariff_is_pricing_exception
```

The runner resolves this workspace from its own path, validates module and tag input, starts only
the Compose database dependency, installs modules into a fresh `sedar_test_*` database, uses an
isolated data directory and HTTP port, and removes its exact test container and database on success,
failure, or interruption. The database ownership marker is set atomically by the same PostgreSQL
statement that creates the database, while the container carries a matching private label. Cleanup
will never delete a resource without its run-specific marker. The runner never accepts a shared
database name. A full run installs
`sedar_demo_suite`; targeted runs install only the selected modules and their dependencies.

Odoo executes matching tests in two phases during module loading: default `at_install` tests after
their module is installed, then `post_install,-at_install` tests after all modules are loaded. The
runner's module-qualified selection preserves both phases. `--test-tags` enables tests, while
`--stop-after-init` exits after initialization. Odoo 19 notes that `--no-http` is ignored when tests
are enabled, so the runner binds the required HTTP server to a unique loopback port instead.

Use Odoo's server-side `Form` helper when a model test must reproduce defaults, onchange behavior,
and relational field editing from a form. Use `HttpCase` and tours for complete browser flows; they
require a Chrome-enabled test image, which the current official Odoo container does not include.
Use `assertQueryCount` only around stable, warmed-cache paths because query counts can change with
cache state and Odoo patch versions. Use Odoo's profiler to diagnose slow code and query patterns,
not as a pass/fail assertion by itself.

References: [Odoo 19 testing](https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html),
[performance](https://www.odoo.com/documentation/19.0/developer/reference/backend/performance.html),
[frontend testing](https://www.odoo.com/documentation/19.0/developer/reference/frontend/unit_testing.html),
and [CLI](https://www.odoo.com/documentation/19.0/developer/reference/cli.html).

There is no GitHub Actions workflow for this repository. Run the Ruff check and the relevant
targeted Odoo tests before review; run the full local suite for changes that cross module boundaries.

## Procurement and Inventory Demo

Open **SEDAR > Procurement** as the configured Procurement and Inventory Officer. The workspace
contains Purchase Requests, Bidder List, Purchase Orders, Storage, and Currently In Use.

The deterministic PM scenario has three requested products and partial supplier coverage:

- Bidder 1 quotes Products A and B and wins both.
- Bidder 2 quotes Product A and does not win.
- Bidder 3 quotes Products B and C and wins Product C.
- The resulting Bidder 1 Purchase Order contains A and B; the Bidder 3 Purchase Order contains C.

Both receipts are standard Odoo Inventory receipts into Storage. The seeded Product A issue is a
standard internal move to the tugboat and remains visible under Currently In Use through its open
Inventory Lifecycle. Equipment Running Hours and related active/history procurement are also visible
from **SEDAR > Fleet Monitoring > AIS Operations Map**. The map is a Simulated AIS Feed; it is not
live tracking or navigational evidence.

Commercial Bid data is restricted to the exact company-configured Officer. An AIS/Maintenance-only
user may open valid Equipment detail but receives a limited payload with commercial identities,
prices, terms, awards, Purchase Order suppliers, and quotation attachments recursively omitted.

## Procurement Release Verification

Run the focused Odoo tests on fresh, disposable databases:

```sh
python3 scripts/run_odoo_tests.py \
  --module sedar_marine_maintenance \
  --module sedar_marine_inventory \
  --module sedar_purchase_request \
  --module sedar_ais_demo \
  --module sedar_demo_suite
```

Then run the isolated legacy upgrade gate:

```sh
python3 scripts/verify_procurement_upgrade.py
```

The upgrade verifier does not use `sedar_demo`. It archives the agreed pre-procurement base into a
temporary workspace, creates a uniquely named Compose project and isolated database/filestore,
captures legacy Purchase Request, Purchase Order, receipt, supplier-bill, Inventory Issue, and stock
move/line/lot facts, then replaces the temporary addons with the candidate tree. A separate clean
candidate database is installed and upgraded, while the legacy database is upgraded twice; every
pass uses the exact shared Compose module list. The gate fails if legacy facts change, the PM fixture
does not have the exact stable record set and A/B-versus-C allocation, or a repeated pass changes
fixture identity or semantic content. Its JSON output records the candidate HEAD, a SHA-256 digest
of every tracked and untracked non-ignored source file, whether the tree was dirty, the Odoo image
ID/digest, database and data path,
commands, exits, and logs.

Successful temporary evidence is removed by default; pass `--keep-success` when an audit copy is
needed. On any failure, the script deliberately leaves the uniquely named Compose project, isolated
database, filestore, report, and logs in the printed temporary directory. Diagnose that evidence,
then remove only the printed project with `docker compose --project-name <printed-project> down`
from the printed temporary `sedar-new` directory. Never use this verifier against a shared database.

The isolated checks do not replace the final real-client walkthrough. Before merging a Procurement
release, upgrade the shared stack, inspect comparison, the two Purchase Orders, receipt → Storage →
issue → Currently In Use, and map active/history/empty states at 1440×900 and 390×844. Inspect the
valid Equipment-detail JSON-RPC payload as a restricted AIS/Maintenance-only user; a screenshot alone
cannot prove server-side commercial redaction.

## Portal Theme

The `sedar_portal_theme` addon provides a shared SEDAR frontend style for the Client Portal,
Applicant Portal, and public application pages. It is a presentation-only integration layer: client
Service Orders, applicant tracking, and recruitment intake continue to be owned by their existing
modules and controllers.

Docker installs and upgrades this module with the rest of the demo stack so portal users receive the
same navy/blue SEDAR branding, typography, buttons, cards, forms, tables, status badges, and mobile
spacing as the internal Odoo theme family.

## Simulated AIS Fleet Monitoring

Open **SEDAR > Fleet Monitoring > AIS Operations Map** for the offline-safe Batangas Bay fleet
dashboard. The screen shows animated fictional tugboat markers, speed, course, position, destination,
current or home crew, active Service Order context, maintenance holds, and dry-dock details. Use
**Advance feed** to move underway tugboats to their next fictional waypoint; browser animation can be
paused independently.

Demo fleet-monitoring credentials:

- Login: `ais@sedar.demo`
- Password: `aisdemo`

Every position and screen is labeled as simulation-only. No Google Maps, AIS provider, GPS device,
or internet connection is used, and the data must not be treated as navigational evidence.

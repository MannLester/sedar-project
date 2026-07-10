# SEDAR Tug Services ERP / Marine Fleet MVP

This repository contains the SEDAR tugboat ERP and marine fleet management MVP plan plus an Odoo Community prototype.

The MVP is based on [resources/Web System.pdf](resources/Web%20System.pdf). It uses generic tugboat business processes and sample data because final SEDAR-specific workflows, rate tables, approvals, and real company records are not available yet.

The demo goal is simple:

"We can build the integrated ERP and marine fleet management foundation. The remaining inputs after deal closing are the actual SEDAR data, approval rules, forms, rate tables, and department-specific business processes."

## What Is Included

- Planning documents for the MVP scope and build phases.
- A PDF-to-dashboard coverage matrix.
- A live backend requirement status in [docs/REQUIREMENT_IMPLEMENTATION_STATUS.md](docs/REQUIREMENT_IMPLEMENTATION_STATUS.md).
- An Odoo Community Docker setup.
- A custom Odoo addon named `sedar_marine_mvp`.
- Seed data for dashboard, vessel, operations, finance, maintenance, HSE, crew, procurement, inventory, HR, and document control records.

## Requirements

Install these before running the project:

- Docker Desktop.
- Git.
- A modern browser.

No local Python, PostgreSQL, or Odoo installation is required. Docker provides Odoo Community and PostgreSQL.

## Quick Start

Clone the repository:

```powershell
git clone https://github.com/MannLester/sedar-project.git
cd sedar-project
```

Start Odoo and PostgreSQL:

```powershell
cd odoo
docker compose up -d
```

Initialize the MVP database and install the SEDAR addon:

```powershell
docker compose exec -T odoo odoo -d sedar_mvp -i sedar_marine_mvp --stop-after-init --no-http
docker compose restart odoo
```

Open Odoo:

```text
http://localhost:8069
```

Select the `sedar_mvp` database.

## First Login

If Odoo asks you to log in, use the database's administrator account created during database setup. If you created the database through the Odoo UI, use the email and password you entered there.

After logging in, open the app switcher. You should see these app areas:

- Management Dashboard.
- Tug Operations.
- Finance and Accounting.
- Technical and Maintenance.
- Crewing.
- Health, Safety, Security and Environment.
- Procurement.
- Inventory Management.
- Human Resources.
- Marketing.
- Document Control.
- Corporate Management.

## Re-running From Scratch

To stop the stack:

```powershell
docker compose down
```

To delete the local database volumes and start fresh:

```powershell
docker compose down -v
docker compose up -d
docker compose exec -T odoo odoo -d sedar_mvp -i sedar_marine_mvp --stop-after-init --no-http
docker compose restart odoo
```

Only use `docker compose down -v` when you are okay deleting your local Odoo database.

## Odoo Community Notes

The Odoo Community source and standard Community apps come from the Docker image:

```text
odoo:19.0
```

We do not vendor the full Odoo Community source into this repository. Project-owned code lives in:

```text
odoo/custom_addons/sedar_marine_mvp
```

See [odoo/community/README.md](odoo/community/README.md) for the source boundary.

## Documents

- [PDF_ANALYSIS.md](PDF_ANALYSIS.md): What the PDF is asking for and how to interpret it for an MVP.
- [PLAN_OF_PROCEEDINGS.md](PLAN_OF_PROCEEDINGS.md): Recommended order for starting and executing the MVP.
- [DASHBOARD_COVERAGE_MATRIX.md](DASHBOARD_COVERAGE_MATRIX.md): Checklist proving every PDF item is represented in the dashboard.
- [MVP_PRESIDENT_DATA_REQUIREMENTS.md](MVP_PRESIDENT_DATA_REQUIREMENTS.md): Data and KPIs a tugboat company president would want.
- [MODULE_CONTENT_SPECIFICATION.md](MODULE_CONTENT_SPECIFICATION.md): Exact owner-facing content and actions for every PDF module.
- [RESEARCH_NOTES.md](RESEARCH_NOTES.md): Public research notes and what can safely be borrowed.
- [odoo/README.md](odoo/README.md): Odoo Community MVP setup and run instructions.
- [phases/01-mvp-alignment-and-demo-scope.md](phases/01-mvp-alignment-and-demo-scope.md): Phase 1 planning.
- [phases/02-core-data-and-mock-data.md](phases/02-core-data-and-mock-data.md): Phase 2 planning.
- [phases/03-core-workflows.md](phases/03-core-workflows.md): Phase 3 planning.
- [phases/04-executive-dashboards.md](phases/04-executive-dashboards.md): Phase 4 planning.
- [phases/05-demo-hardening-and-handoff.md](phases/05-demo-hardening-and-handoff.md): Phase 5 planning.

## Current MVP Status

The current Odoo prototype is functional but not final presentation polish. It proves:

- The Odoo Community environment runs locally.
- The custom SEDAR addon installs.
- Every major PDF module is represented.
- The app navigation is split into department-style Odoo app areas.
- Demo data loads for dashboard and module records.

Next work should focus on a more professional President Dashboard UI and richer end-to-end demo workflows.

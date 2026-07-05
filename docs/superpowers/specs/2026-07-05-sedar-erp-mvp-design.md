# SEDAR Tug Services — ERP MVP Design

## Background

SEDAR Tug Services, Inc. (a Philippine tugboat operator) wants a centralized ERP/Marine
Fleet Management system unifying Finance, Tug Operations, Technical/Maintenance, Crewing,
HSSE, Procurement, Inventory, HR, Document Control, and Executive Management. The client
has not shared detailed business-process information and is withholding it until an MVP
is demonstrated. Source of requirements: `resources/Web System.txt` (client's internal
memo, which also recommends Odoo as the core platform).

The MVP must cover **every module listed in the client's document**, at basic
(non-workflow-automated) functionality, so the client can see the full shape of the
system before providing deeper process detail.

## Goal

Produce a working Odoo-based prototype — not just a document — that the team can run on
another machine to demo to SEDAR's leadership, plus a written spec (this document)
enumerating every tab, its fields, and its functionality per module.

## Constraints

- Odoo **Community Edition** only (no Enterprise license available in this environment).
  This means full General Ledger, Budgeting, Fixed Assets, Payroll, Documents app, and
  Spreadsheet/BI dashboards are **not available** and are explicitly out of MVP scope
  (see "Out of scope" below). Community's Invoicing app covers basic AR/AP.
- No public hosting in this sandbox — deliverable is a portable `docker-compose` setup
  plus custom addons in this git repo, runnable elsewhere.
- Demo data must be realistic Philippine tugboat-industry style (PHP currency, MARINA/
  PPA/PCG-style permits and certificates, named vessels, local ports) to make the pitch
  concrete.

## Architecture

- **Odoo 17.0 Community Edition** + **PostgreSQL 15**, orchestrated via `docker-compose.yml`.
- Repo layout:
  - `docker-compose.yml`, `config/odoo.conf`
  - `addons/sedar_tug_ops/`
  - `addons/sedar_hsse/`
  - `addons/sedar_crewing/`
  - `addons/sedar_doccontrol/`
  - `addons/sedar_dashboard/`
  - `scripts/seed_data.py` — idempotent script that loads demo records via Odoo's
    external API (or XML data files) after modules are installed
  - `docs/` — this spec, plus a screenshot walkthrough captured after the prototype runs
- Each custom department is its own installable Odoo module (not one giant module), so
  departments can be independently extended later. Each module follows standard Odoo
  structure: `models/`, `views/`, `security/ir.model.access.csv`, `__manifest__.py`.
- Native Community apps are installed and configured (not rebuilt): **Invoicing**,
  **Purchase**, **Inventory**, **Maintenance**, **Employees**, **Recruitment**.

## Module scope

### B. Native Odoo Community apps (configured, not custom-built)

| Client Dept | Odoo App | MVP Tabs/Views |
|---|---|---|
| Finance & Accounting (basic only) | Invoicing | Customer Invoices, Vendor Bills, Payments, basic P&L/Balance Sheet report |
| Procurement | Purchase | Purchase Requests (RFQ), Purchase Orders, Vendors, 2-step approval workflow |
| Inventory | Inventory | Products (spare parts/fuel/lube/office supplies), Warehouses, Stock Moves, barcode-ready fields |
| Technical/Maintenance | Maintenance | Equipment (linked to vessels via custom field), Maintenance Requests, Preventive Maintenance calendar |
| HR | Employees + Recruitment | Employee records, Attendance, Recruitment pipeline, basic performance note field |

### C. Custom modules (built from scratch)

**1. Tug Operations (`sedar_tug_ops`)**
- **Vessels**: name, IMO/registry no., type (tug/barge), capacity, status (active/dry
  dock/standby)
- **Job Orders / Dispatch**: customer, vessel assigned, origin/destination port,
  requested date, status (requested → dispatched → in progress → completed → billed)
- **Voyage Log**: departure/arrival timestamps, distance, weather notes, linked job order
- **Fuel Monitoring**: vessel, date, liters consumed, cost, running consumption view
- **Towage Billing**: rate basis (per hour/per job), computed amount, link to draft
  Invoice (Invoicing app)
- GPS/AIS: placeholder lat/long fields only — no live feed integration (Phase 2)

**2. HSSE (`sedar_hsse`)**
- **Incidents**: date, vessel/location, severity, description, corrective action, status
- **Near-Miss Reports**: reporter, description, risk category
- **Inspections & Audits**: type, checklist (pass/fail lines), auditor, date, findings
- **Risk Assessments**: activity, hazard, likelihood/severity score, mitigation
- **Permits**: permit type, issuing authority (MARINA/PCG/PPA), issue/expiry date,
  status auto-flags when nearing expiry

**3. Crewing (`sedar_crewing`)**
- **Crew Roster**: employee (linked to HR Employees), rank/position, current vessel
  assignment
- **Rotation Schedule**: on/off-board dates, vessel, rotation status
- **Certifications**: STCW cert type, issue/expiry date, expiry-alert flag
- **Medical Certificates**: exam date, expiry, fit-for-duty status
- **Leave**: type, dates, approval status
- Payroll: reference link to HR/Invoicing only, no computation logic (Phase 2 — Odoo
  Payroll is Enterprise-only)

**4. Document Control (`sedar_doccontrol`)**
- **Contracts**: counterparty, type, effective/expiry dates, file attachment
- **Vessel Certificates**: cert type, vessel, issuing body, expiry
- **Insurance**: policy no., insurer, coverage type, expiry
- **Permits/Board Resolutions/ISO Docs**: category, reference no., file attachment,
  status
- Shared expiry-alert logic reused across all document tabs

**5. Management Dashboard (`sedar_dashboard`)**
- Single-page KPI view (Community-compatible, no Enterprise Spreadsheet/BI): count of
  active jobs, vessel utilization %, open incidents, expiring certs/permits, monthly
  invoiced revenue — computed live from the modules above.

## Out of scope for MVP (Phase 2)

Full multi-currency General Ledger, Budgeting, Fixed Assets, Payroll processing, real
AIS/GPS feed integration, Power BI, DocuSign, Microsoft 365 integration, ISO
document version-control workflows, mobile app. These require either Odoo Enterprise
licensing or third-party integrations not feasible for a no-budget MVP demo.

## Testing / verification

- Each custom module installs cleanly with no errors (`docker compose up`, install via
  Odoo Apps menu or `-i` flag).
- Seed script populates demo data across every tab so no view is empty during a demo.
- Manual click-through of every tab listed above, confirming CRUD works and computed
  fields (billing amount, KPI counts, expiry flags) display correctly.

## Deliverables

1. This spec document.
2. Git repo containing `docker-compose.yml`, custom addons, seed script.
3. Screenshot walkthrough of every tab (captured after the prototype is running), saved
   under `docs/`.

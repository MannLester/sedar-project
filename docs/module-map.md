# SEDAR Module Map

SEDAR is one Odoo 19 application made of 29 addons in `sedar-new/custom-addons/<domain>/<addon>`.
The folder is the domain, so this map is also the folder layout. The authoritative grouping, public surfaces, and limits live in
`sedar-new/architecture/boundaries.toml` and are enforced by `make check` (ADR-0011).

## How the pieces fit

```text
Client request (portal / Marketing)
  -> Service Order (sedar_marine_operations)
  -> readiness gate: tug (maintenance) + crew (compliance, availability, scheduling) + stock (inventory)
  -> Marine Operation (sedar_marine_dispatch) executed by Tug Masters
  -> Service Completion -> Billing Review -> draft invoice (sedar_marine_finance -> Odoo Accounting)
Shortage -> Manpower Request -> vacancy -> applicant -> employee -> marine crew
Purchase Request -> Bids -> Line Awards -> Purchase Orders -> receipts -> stock -> readiness
```

Addons talk through Python model inheritance, stored computed fields, and the public methods and
models each addon declares. Dependencies only point one way: an addon may depend on addons
beneath it, never above it.

## Rules

- Every addon belongs to exactly one domain in `boundaries.toml`, and its folder is that domain. Moving an addon means changing both, and the `domain-folder` check fails if they disagree.
- New domain folders must also be added to `addons_path` in `sedar-new/config/odoo.conf`.
- Another addon may only use models its owner lists under `[public_models]`, and the manifest must depend on the owner.
- Methods other addons call are public by name and decorated with `@api.private`; underscore methods are private to the addon.
- Production addons never depend on demonstration addons.
- Add a new addon to `SEDAR_MODULES` in `sedar-new/docker-compose.yml` so a clean start installs it.

## Domains

### Marine services (`marine`)

| Addon | Purpose | Depends on (SEDAR) |
| --- | --- | --- |
| `sedar_marine_operations` | Client service-order intake, tariffs, and marine operations planning | `sedar_document_control` |
| `sedar_marine_dispatch` | Dispatch and execution tracking for marine service orders | `sedar_marine_operations` |
| `sedar_marine_finance` | Billing review and Odoo invoicing for completed marine services | `sedar_marine_operations`, `sedar_marine_dispatch` |
| `sedar_marine_maintenance` | Marine maintenance, defects, dry dock planning, and tug availability controls | `sedar_marine_operations`, `sedar_marine_dispatch` |
| `sedar_marine_inventory` | Marine inventory readiness, spare parts, fuel, and lubricant controls | `sedar_marine_dispatch`, `sedar_marine_maintenance`, `sedar_marine_dispatch_demo` |
| `sedar_hsse` | HSSE incidents, inspections, risk assessments, permits, meetings, training, and corrective actions | `sedar_document_control`, `sedar_marine_maintenance`, `sedar_marine_dispatch` |

### People and crewing (`people`)

| Addon | Purpose | Depends on (SEDAR) |
| --- | --- | --- |
| `sedar_manpower_planning` | Review marine crew shortages and approve manpower demand | `sedar_marine_dispatch` |
| `sedar_crew_compliance` | Controls crew credential and medical evidence, renewal, and readiness impact | `sedar_document_control`, `sedar_marine_operations`, `sedar_recruitment_crewing` |
| `sedar_crewing_availability` | Tracks dated crew unavailability, leave, training blockers, and temporary relief | `sedar_crew_compliance`, `sedar_manpower_planning` |
| `sedar_crew_scheduling` | Adds crew rotation planning, assignment confirmation controls, and scheduling views | `sedar_marine_dispatch`, `sedar_crewing_availability` |
| `sedar_careers` | Publish approved SEDAR vacancies to the public Careers website | `sedar_manpower_planning` |
| `sedar_applicant_intake` | Public ADM-3 applicant intake and initial document submission | `sedar_careers`, `sedar_document_control` |
| `sedar_applicant_portal` | Authenticated applicant dashboard and secure application tracking | `sedar_applicant_intake` |
| `sedar_recruitment_operations` | HR applicant processing dashboard and controlled recruitment stages | `sedar_applicant_portal`, `sedar_document_control` |
| `sedar_recruitment_crewing` | Creates controlled marine crew onboarding after applicant-to-employee conversion | `sedar_recruitment_operations`, `sedar_manpower_planning`, `sedar_marine_operations` |

### Supply (`supply`)

| Addon | Purpose | Depends on (SEDAR) |
| --- | --- | --- |
| `sedar_purchase_request` | Department purchase request approval and standard Purchase Order handoff | `sedar_marine_inventory` |

### Customer (`customer`)

| Addon | Purpose | Depends on (SEDAR) |
| --- | --- | --- |
| `sedar_marketing` | Customer-centred service request, quotation, contract, appointment, and relationship workspace | `sedar_marine_operations`, `sedar_marine_finance`, `sedar_document_control`, `sedar_theme` |

### Platform (`platform`)

| Addon | Purpose | Depends on (SEDAR) |
| --- | --- | --- |
| `sedar_document_control` | SEDAR document catalogue, typed fields, and employee requests | none |
| `sedar_executive_dashboard` | Corporate document registers and source-backed executive KPIs | `sedar_document_control`, `sedar_hsse`, `sedar_purchase_request`, `sedar_marine_inventory`, `sedar_marine_maintenance`, `sedar_crew_compliance`, `sedar_manpower_planning` |
| `sedar_theme` | Reference-inspired sidebar theme for the SEDAR Odoo MVP | `sedar_document_control`, `sedar_marine_operations`, `sedar_marine_finance`, `sedar_purchase_request` |
| `sedar_portal_theme` | Shared SEDAR visual language for client and applicant portals | `sedar_theme`, `sedar_marketing`, `sedar_marine_operations`, `sedar_applicant_intake`, `sedar_applicant_portal` |
| `sedar_ui_cards` | Reusable backend card design primitives for SEDAR modules | none |

### Demonstration (`demo`)

| Addon | Purpose | Depends on (SEDAR) |
| --- | --- | --- |
| `sedar_ais_demo` | Offline-safe simulated AIS/GPS fleet map for client demonstrations | `sedar_marine_dispatch_demo`, `sedar_marine_maintenance`, `sedar_crew_scheduling`, `sedar_purchase_request` |
| `sedar_erp_demo` | Demonstration-only HR, Finance, and CRM extensions using shared Odoo records | `sedar_marine_finance`, `sedar_marine_operations`, `sedar_service_order_demo`, `sedar_recruitment_crewing` |
| `sedar_service_order_demo` | Fictional service orders, tugboats, crew, and readiness scenarios | `sedar_marine_operations`, `sedar_marine_finance` |
| `sedar_marine_dispatch_demo` | Fictional dispatch and execution scenarios | `sedar_marine_dispatch`, `sedar_service_order_demo` |
| `sedar_manpower_planning_demo` | Fictional shortage review and manpower request scenarios | `sedar_manpower_planning`, `sedar_careers`, `sedar_service_order_demo`, `sedar_marine_dispatch_demo` |
| `sedar_recruitment_demo` | Repeatable fictional recruitment scenarios for the SEDAR demonstration | `sedar_recruitment_operations`, `sedar_manpower_planning_demo`, `sedar_marine_dispatch_demo`, `sedar_applicant_intake` |
| `sedar_demo_suite` | Final deterministic reconciliation for the SEDAR demonstration | `sedar_service_order_demo`, `sedar_marine_dispatch_demo`, `sedar_manpower_planning_demo`, `sedar_recruitment_demo`, `sedar_recruitment_crewing`, `sedar_crew_compliance`, `sedar_crewing_availability`, `sedar_crew_scheduling`, `sedar_marine_maintenance`, `sedar_marine_inventory`, `sedar_purchase_request`, `sedar_hsse`, `sedar_erp_demo`, `sedar_executive_dashboard`, `sedar_marketing`, `sedar_ais_demo`, `sedar_theme`, `sedar_portal_theme`, `sedar_ui_cards` |

## Known boundary debt

`architecture/baseline.json` lists the violations that existed when the checks were introduced.
The main ones:

- `sedar_marine_inventory` depends on `sedar_marine_dispatch_demo`. Its install hook seeds demonstration records and relies on that load order, so removing the dependency breaks demo seeding until the seeding moves into demonstration addons.
- `sedar_marine_maintenance` and `sedar_recruitment_crewing` reference demonstration records through soft `env.ref` lookups.
- 11 files exceed the size limits (single classes over 400 lines, large demo hooks, and four XML view files) and 61 models or fields are missing from `docs/custom-models.md`.

The baseline may only shrink. Remove entries with `make baseline` after fixing them.

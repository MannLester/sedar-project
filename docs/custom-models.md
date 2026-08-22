# Custom Model Reference

This document records the Odoo models and fields introduced or extended by the SEDAR service-completion, finance, applicant portal, and recruitment-operations MVP. It covers the local changes built on top of the existing Marine Operations, Marine Dispatch, Odoo Accounting, Odoo Recruitment, and SEDAR Document Control models. It does not attempt to document unrelated models owned by the manpower, applicant-intake, or careers modules.

Update this document in the same change whenever a listed custom field is added, renamed, removed, or given a materially different workflow meaning.

P0 implementation note: `sedar_demo_suite` adds a method-only `res.company` reconciliation
(`sedar_reconcile_demo_suite`) that is intentionally idempotent and runs after dependency
installation and on upgrade. It repairs the flagship completed-operation scenarios,
loads Odoo's generic chart of accounts only when a fresh demo company has no accounting
foundation, creates linked accounting/procurement demonstration records, and does not
introduce a new business model. It also adds moderate, idempotent dashboard-volume
fixtures for Service Orders, standard Odoo invoices, maintenance work orders, purchase
requests, HSSE records, inventory items/issues, and controlled documents so demonstration
list views do not appear empty. It preserves one tug-compatible, stock-derived Job Order
shortage so the Procurement Inventory Check demonstration includes both Ready and Shortage
requirements. For the local demonstration only, reconciliation grants Odoo's built-in
Administrator and every active, internal `@sedar.demo` persona the highest SEDAR manager role
in every installed workspace so every visible sidebar destination opens without switching
accounts. Customer, applicant, and other shared portal users remain restricted. This temporary
Demo Access Override must be replaced with role-scoped groups and permission-aware navigation
after the demonstration.
Odoo Accounting continues to own the resulting journals,
accounts, invoices, payments, and ledger lifecycle. `sedar.maintenance.part.line.stock_move_ids` and
`sedar.operation.fuel.log.stock_move_ids` link operational issue/consumption records to
standard Odoo `stock.move` records; direct quant updates remain limited to opening-balance
fixture seeding.

## Model summary

| Model | Change type | Purpose | Main source |
| --- | --- | --- | --- |
| `sedar.tug.assignment` | Extended | Records the assigned Tug Master's actual service time and completion declaration for one tug | `sedar_marine_operations/models/marine_crew.py` |
| `sedar.marine.service.order` | Extended | Applies automated tug/crew/inventory readiness, aggregates tug completions, freezes confirmed pricing, tracks billing/payment, and surfaces HSSE exceptions | `sedar_marine_operations/models/marine_service_order.py`; `sedar_marine_dispatch/models/marine_service_order.py`; `sedar_marine_finance/models/marine_finance.py`; `sedar_hsse/models/hsse.py` |
| `sedar.marine.operation` | Workflow changed | Provides the automatically created execution record whose time and completion follow Tug Master records | `sedar_marine_dispatch/models/marine_operation.py` |
| `sedar.client.tariff` | Extended | Governs client- and terminal-specific tariff approval and revision history | `sedar_marine_finance/models/marine_finance.py` |
| `sedar.marine.billing.adjustment` | New | Stores explained charges or deductions included in the final invoice | `sedar_marine_finance/models/marine_finance.py` |
| `account.move` | Extended | Links the standard Odoo customer invoice back to its Marine Service Order | `sedar_marine_finance/models/account_move.py` |
| `res.company` | Extended | Configures the Procurement and Inventory Officer, demo currency, and repeatable fictional recruitment and crew-onboarding demonstration records | `sedar_purchase_request/models/purchase_request.py`; `sedar_service_order_demo/models/res_company.py`; `sedar_recruitment_demo/models/res_company.py`; `sedar_recruitment_crewing/models/res_company.py` |
| `res.users` | Method-only extension | Assigns the custom Service Order dashboard as the default home action for internal users | `sedar_theme/models/res_users.py` |
| `hr.recruitment.stage` | Extended | Maps internal recruitment stages to applicant-visible statuses and instructions | `sedar_applicant_portal/models/portal.py` |
| `hr.applicant` | Extended | Owns portal access, public tracking, HR processing, interviews, requirements, employee conversion, and the marine crewing handoff | `sedar_applicant_portal/models/portal.py`; `sedar_recruitment_operations/models/applicant.py`; `sedar_recruitment_crewing/models/applicant.py` |
| `hr.employee` | Extended | Preserves traceability from successful applicant conversion into the HR employee master, controls generic HR onboarding, and exposes linked marine crew onboarding cases | `sedar_recruitment_operations/models/employee.py`; `sedar_recruitment_crewing/models/employee.py` |
| `sedar.crew.onboarding` | New | Controls the handoff from a marine employee to a deployment-eligible Crew Profile | `sedar_recruitment_crewing/models/crew_onboarding.py` |
| `sedar.crew.certificate` | Extended | Links crew credentials and medicals to controlled document evidence, renewal status, and readiness eligibility | `sedar_crew_compliance/models/crew_certificate.py`; `sedar_crew_compliance/models/crew_assignment.py`; `sedar_crew_compliance/models/crew_onboarding.py` |
| `sedar.crew.unavailability` | New | Stores dated leave, medical, training, and temporary crew availability blockers | `sedar_crewing_availability/models/crew_unavailability.py` |
| `hr.leave` | Extended | Synchronizes approved Odoo Time Off into dated Crew Unavailability records | `sedar_crewing_availability/models/hr_leave.py` |
| `sedar.crew.shortage.action` | Extended | Records medical/training unavailability evidence and temporary relief crew assignments | `sedar_crewing_availability/models/shortage_action.py` |
| `sedar.crew.assignment` | Extended | Adds scheduling status, calendar fields, confirmation controls, and replacement suggestions | `sedar_crew_scheduling/models/crew_assignment.py` |
| `sedar.crew.rotation` | New | Plans crew rotation periods, watch, tugboat, relief crew, and handover | `sedar_crew_scheduling/models/crew_rotation.py` |
| `sedar.tugboat` | Extended | Owns each fleet asset by company and exposes technical equipment, maintenance blockers, dry-dock plans, readiness reason, tugboat stock location, and HSSE exceptions | `sedar_marine_operations/models/marine_crew.py`; `sedar_marine_maintenance/models/tugboat.py`; `sedar_marine_inventory/models/tugboat.py`; `sedar_hsse/models/hsse.py` |
| `sedar.ais.position` | New | Stores the current fictional AIS/GPS report consumed by the offline fleet-monitoring demonstration | `sedar_ais_demo/models/ais_position.py` |
| `maintenance.equipment` | Extended | Links standard Odoo equipment to tugboats, running-hour history, and persistent Replacement Equipment inventory provenance | `sedar_marine_maintenance/models/maintenance_equipment.py`; `sedar_marine_inventory/models/inventory_lifecycle.py` |
| `sedar.equipment.running.hour.reading` | New | Preserves dated, attributable Equipment hour-meter observations and manager-controlled corrections | `sedar_marine_maintenance/models/maintenance_equipment.py` |
| `maintenance.request` | Extended | Adds SEDAR work-order type, tug availability impact, release evidence, dry-dock linkage, and spare-part status/lines | `sedar_marine_maintenance/models/maintenance_request.py`; `sedar_marine_inventory/models/maintenance_parts.py` |
| `sedar.drydock.plan` | New | Represents dry-dock planning, milestones, availability impact, and controlled release | `sedar_marine_maintenance/models/drydock.py` |
| `sedar.drydock.milestone` | New | Tracks planned and actual dry-dock milestones | `sedar_marine_maintenance/models/drydock.py` |
| `sedar.inventory.template` | New | Defines stock-backed inventory requirements generated for a Service Order service type | `sedar_marine_inventory/models/inventory_models.py` |
| `sedar.inventory.template.line` | New | Defines product quantities required by an inventory template | `sedar_marine_inventory/models/inventory_models.py` |
| `sedar.inventory.requirement` | New | Stores generated or manual stock requirements that drive the inventory component of readiness | `sedar_marine_inventory/models/service_order.py` |
| `product.product` | Extended | Provides the SEDAR Inventory Check item identity, warehouse availability, reorder status, and tug compatibility | `sedar_marine_inventory/models/inventory_item.py` |
| `res.company` | Extended | Owns the exact Procurement and Inventory Officer and configured Storage, consumption, and disposal locations | `sedar_marine_inventory/models/res_company.py` |
| `stock.location` | Extended | Tags authoritative SEDAR Storage, tugboat, consumption, and disposal locations | `sedar_marine_inventory/models/stock_location.py` |
| `sedar.inventory.issue` | New | Preserves the immutable audit record and completed Storage-to-tugboat movement for an Inventory Issue | `sedar_marine_inventory/models/inventory_item.py` |
| `sedar.inventory.lifecycle` | New | Tracks issued goods as Currently In Use until explicit return, consumption, or disposal | `sedar_marine_inventory/models/inventory_lifecycle.py` |
| `sedar.inventory.lifecycle.event` | New | Stores append-only technical and stock-disposition events for a lifecycle | `sedar_marine_inventory/models/inventory_lifecycle.py` |
| `sedar.maintenance.part.line` | New | Tracks requested, reserved, issued, and consumed spare parts for maintenance work orders | `sedar_marine_inventory/models/maintenance_parts.py` |
| `sedar.operation.fuel.log` | New | Tracks operation fuel/lubricant issue, consumption, and remaining balance by tugboat | `sedar_marine_inventory/models/operation_fuel.py` |
| `sedar.marine.operation` | Extended | Exposes operation fuel/lubricant logs and consumption summary | `sedar_marine_inventory/models/operation_fuel.py` |
| `sedar.purchase.request` | New | Captures confirmed internal physical-goods needs, internal review, procurement progress, and links to resulting standard Purchase Orders | `sedar_purchase_request/models/purchase_request.py` |
| `sedar.purchase.request.line` | New | Captures requested products, quantities, estimated costs, and maintenance/inventory source traceability | `sedar_purchase_request/models/purchase_request.py` |
| `sedar.purchase.bid` | New | Preserves one supplier quotation for one Purchase Request, including private evidence, commercial terms, lifecycle, and audit facts | `sedar_purchase_request/models/purchase_bid.py` |
| `sedar.purchase.bid.line` | New | Records the subset of requested products quoted by one Bidder at full requested quantities and supplier prices | `sedar_purchase_request/models/purchase_bid.py` |
| `sedar.purchase.line.award` | New | Preserves immutable product-level winner, commercial snapshots, reset audit, and Purchase Order line handoff history | `sedar_purchase_request/models/purchase_award.py` |
| `sedar.purchase.line.award.wizard` | New transient | Captures one received Bid line, required best-value reason, and explicit expiry/zero-price exceptions | `sedar_purchase_request/models/purchase_award.py` |
| `sedar.purchase.line.award.reset.wizard` | New transient | Captures the mandatory reason for resetting an unordered Line Award | `sedar_purchase_request/models/purchase_award.py` |
| `sedar.purchase.request.line.cancel.wizard` | New transient | Captures the mandatory reason for irreversibly cancelling one unawarded requested product | `sedar_purchase_request/models/purchase_award.py` |
| `sedar.purchase.request.recovery.wizard` | New transient | Captures the Officer's reason for recovering an incomplete legacy handoff | `sedar_purchase_request/models/purchase_award.py` |
| `ir.attachment` | Method-only extension | Protects Bid quotation files from public/token access, reassignment, and post-receipt mutation | `sedar_purchase_request/models/ir_attachment.py` |
| `purchase.order` | Extended | Links each standard Purchase Order to the Purchase Request and exact winning Bid that produced it | `sedar_purchase_request/models/purchase_request.py`; `sedar_purchase_request/models/purchase_award.py` |
| `purchase.order.line` | Extended | Links each grouped order line to its requested product, winning Bid line, and immutable Line Award | `sedar_purchase_request/models/purchase_award.py` |
| `sedar.hsse.incident` | New | Tracks incidents, near misses, investigation, source links, confidential evidence, corrective actions, and verified closure | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.inspection` | New | Tracks HSSE inspections, source links, findings, overdue counts, and verification | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.inspection.finding` | New | Tracks checklist findings, assigned owner, due date, overdue state, and corrective-action conversion | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.risk.assessment` | New | Tracks hazards, controls, likelihood, impact, residual risk, owner, approval, and linked actions | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.permit` | New | Tracks operational permits, validity, controlled evidence links, and expired-permit exceptions | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.corrective.action` | New | Tracks corrective actions, due dates, evidence, overdue state, critical controls, completion, and verification | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.meeting` | New | Tracks safety meetings, attendance, topics, minutes, source links, and follow-up actions | `sedar_hsse/models/hsse.py` |
| `sedar.hsse.training.record` | New | Tracks HSSE training completion, expiry, evidence, and crew-readiness applicability | `sedar_hsse/models/hsse.py` |
| `sedar.hr.performance.review` | New | Demonstration-only employee performance review history because Odoo Appraisals is unavailable in the shared edition | `sedar_erp_demo/models/erp_demo.py` |
| `sedar.hr.payroll.input` | New | Demonstration-only payroll input facts sourced from standard Attendance, Time Off, and eligible crew records | `sedar_erp_demo/models/erp_demo.py` |
| `sedar.finance.budget` | New | Demonstration-only budget-versus-actual source because the shared edition has no installable budget module | `sedar_erp_demo/models/erp_demo.py` |
| `sedar.fixed.asset` | New | Demonstration-only straight-line fixed-asset and depreciation view because the shared edition has no installable fixed-asset module | `sedar_erp_demo/models/erp_demo.py` |
| `crm.lead` | Extended | Links a CRM opportunity to the interested assisted vessel and resulting SEDAR Service Order | `sedar_erp_demo/models/erp_demo.py` |
| `sedar.document` | Extended | Adds corporate ownership, validity, renewal, confidentiality, related object, and governance status metadata | `sedar_executive_dashboard/models/corporate.py` |
| `sedar.corporate.record` | New | Structured corporate governance register for contracts, vessel certificates, insurance, resolutions, ISO, legal, and audit records | `sedar_executive_dashboard/models/corporate.py` |
| `sedar.executive.dashboard` | New | Computes executive indicators from authoritative Finance, Operations, HR, Maintenance, Inventory, Procurement, HSSE, and Document Control sources | `sedar_executive_dashboard/models/dashboard.py` |
| `sedar.applicant.portal.event` | New | Stores applicant-visible timeline events | `sedar_applicant_portal/models/portal.py` |
| `sedar.applicant.stage.history` | New | Provides an auditable history of HR stage changes | `sedar_recruitment_operations/models/applicant.py` |
| `sedar.applicant.interview` | New | Coordinates interview scheduling, applicant responses, calendar events, and ADM-4 appraisal | `sedar_recruitment_operations/models/interview.py` |
| `sedar.applicant.offer` | New | Records the HR hiring decision, offer issue, applicant response, and ADM-5 gate | `sedar_recruitment_operations/models/offer.py` |
| `sedar.manpower.request` | Workflow changed | Closes approved headcount demand only after linked vacancies are filled | `sedar_manpower_planning/models/manpower_models.py` |
| `sedar.job.vacancy` | Workflow changed | Synchronizes filled openings from traceable employee conversions | `sedar_manpower_planning/models/manpower_models.py` |
| `sedar.document.request` | Extended | Links controlled document requests to applicants and interviews and governs portal/internal recruitment visibility | `sedar_recruitment_operations/models/interview.py`; `sedar_recruitment_operations/security/sedar_recruitment_security.xml` |

## `sedar.tug.assignment`

One record represents one tug assigned to a Service Order. The completion fields are maintained by the assigned Tug Master. Finance or a completion reviewer may return a submitted declaration for correction.

| Field | Type | How it is used |
| --- | --- | --- |
| `order_state` | Related selection | Exposes the parent Service Order state in assignment views and workflow checks. |
| `tug_master_profile_id` | Computed, stored many-to-one to `sedar.crew.profile` | Resolves the active assigned crew member whose rank code is `MASTER`. |
| `tug_master_user_id` | Computed, stored many-to-one to `res.users` | Connects the resolved Tug Master to an Odoo login and enforces that only that user may maintain the declaration. |
| `completion_state` | Selection | Tracks `pending`, `submitted`, or `returned`. Only workflow actions may change it. |
| `actual_start` | Datetime | Actual start declared by the Tug Master; used in actual-duration and billing calculations. |
| `actual_end` | Datetime | Actual end declared by the Tug Master; must be later than `actual_start`. |
| `completion_note` | Text | Required operational account of the completed work. |
| `completion_evidence` | Attachment-backed binary | Optional evidence supporting the Tug Master's declaration. |
| `completion_evidence_filename` | Character | Preserves the uploaded evidence filename. |
| `completion_declared_by_id` | Read-only many-to-one to `res.users` | Audit identity written when completion is submitted. |
| `completion_declared_at` | Read-only datetime | Audit timestamp written when completion is submitted. |
| `completion_return_reason` | Text | Required explanation when a submitted declaration is returned for correction. |

Key behavior:

- `action_declare_complete()` validates role, assignment, service state, actual times, and the completion note before submission.
- `action_return_completion()` unlocks a submitted declaration for correction and requires a reason.
- `_check_actual_times()` rejects zero-length or negative service periods.
- `create()` and `write()` protect completion and audit fields from bypassing workflow actions.
- Any completion or assignment-state change calls the parent order's `_sync_completion_from_tugs()`.

## `sedar.marine.service.order`

The existing Service Order remains the workflow aggregate. Operations determines when every required tug has declared completion. Finance then uses the same record as its billing-review workspace.

### Company ownership

| Model and field | Type | How it is used |
| --- | --- | --- |
| `sedar.tugboat.company_id` | Required indexed many-to-one to `res.company` | Owns the fleet asset, defaults to the active company, is not copied, and cannot change after creation. Tugboat reads are limited to allowed companies, and company-owned operational/stock links must match it. |
| `sedar.marine.service.order.company_id` | Required indexed many-to-one to `res.company` | Owns the complete operational aggregate. It defaults to the active company, is not copied, and cannot change after creation. Client and requesting-contact links are company-checked. |
| `sedar.tug.assignment.company_id` | Stored indexed related many-to-one to `res.company` | Inherits the Service Order company through the company-checked `order_id`. |
| `sedar.manning.requirement.company_id` | Stored indexed related many-to-one to `res.company` | Inherits company through the company-checked tug assignment. |
| `sedar.crew.assignment.company_id` | Stored indexed related many-to-one to `res.company` | Inherits company through the company-checked manning requirement and Service Order. |
| `sedar.crew.shortage.company_id` | Stored indexed related many-to-one to `res.company` | Inherits company through the company-checked manning requirement and Service Order. |
| `sedar.crew.shortage.action.company_id` | Stored indexed related many-to-one to `res.company` | Inherits the operational shortage company and scopes resolution history to allowed companies. |
| `sedar.marine.operation.company_id` | Stored indexed related many-to-one to `res.company` | Inherits company through the company-checked Service Order link. |
| `sedar.marine.operation.tug.company_id` | Stored indexed related many-to-one to `res.company` | Inherits the Marine Operation company; its tug assignment must belong to the same Service Order. |
| `sedar.marine.operation.crew.company_id` | Stored indexed related many-to-one to `res.company` | Inherits the operation-tug company; an optional crew assignment must belong to that operation tug's assignment. |
| `sedar.marine.operation.log.company_id` | Stored indexed related many-to-one to `res.company` | Inherits the Marine Operation company; an optional operation tug must belong to the selected operation. |
| `sedar.marine.operation.delay.company_id` | Stored indexed related many-to-one to `res.company` | Inherits the Marine Operation company; an optional operation tug must belong to the selected operation. |

Global allowed-company record rules isolate Tugboats, the Service Order, and every listed operational descendant. Customer portal lookups retain their explicit client-ownership check and also filter the enabled Odoo companies even though the controller uses elevated reads. Manpower Requests and lines also inherit their own company boundary, and operational shortage evidence may be linked only when it belongs to that same company. The Service Order upgrade migration infers one company from existing Service Order ownership, company-owned client/contact records, invoices, Purchase Requests, or inventory source locations; it aborts on conflicts and otherwise falls back deterministically to the main company. The later Tugboat migration instead requires exactly one company from existing ownership, assignment, stock-location, Inventory Issue, or Equipment evidence and aborts with Tugboat IDs when evidence is missing or conflicting. Company-neutral HSSE, Marketing, tariff, and other master configuration remain outside this aggregate boundary.

### Completion fields

| Field | Type | How it is used |
| --- | --- | --- |
| `tug_completion_count` | Computed, stored integer | Counts active tug assignments whose completion is submitted. |
| `all_tugs_complete` | Computed, stored boolean | Becomes true only when at least the requested number of active tug assignments exists and every active assignment is submitted. |
| `inventory_ready` | Tracked boolean | Historical readiness flag. Slice 11 writes this from stock-derived inventory requirement lines when they exist; the earlier manual confirmation remains only for records with no generated requirements. |
| `inventory_ready_by_id` | Read-only many-to-one to `res.users` | Audit identity of the authorized Operations user who confirmed inventory readiness. |
| `inventory_ready_at` | Read-only datetime | Audit time of the current inventory confirmation. |
| `inventory_requirement_ids` | One-to-many to `sedar.inventory.requirement` | Stock-backed products and quantities required before execution. |
| `inventory_requirement_count` | Computed, stored integer | Counts Service Order inventory requirement lines. |
| `inventory_auto_ready` | Computed, stored boolean | True only when at least one inventory requirement exists and all requirement lines have enough available stock. |
| `inventory_shortage_summary` | Computed, stored character | Summarizes the first stock shortages shown in readiness reason. |

The `readiness_status` selection includes `waiting_inventory`. Before Slice 11, relevant changes to service, scope, tug requirements, terminal, schedule, cargo, permits, or safety requirements cleared the manual inventory confirmation. Slice 11 regenerates stock-backed requirements for planned/blocked/ready orders when relevant service inputs change and uses those lines as the inventory readiness truth. Automated dispatch creates one awaiting-start Marine Operation only when tugboat, crew, and inventory readiness all pass.

`_sync_completion_from_tugs()` moves a dispatched or in-progress order to `completed` when all required tugs are complete. Returning or removing a completion moves a completed order back to `in_progress`.

### Billing and pricing fields

| Field | Type | How it is used |
| --- | --- | --- |
| `terminal_id` | Many-to-one to `sedar.marine.berth` | Identifies the service terminal and narrows tariff matching to the selected port. |
| `confirmed_tariff_id` | Read-only many-to-one to `sedar.client.tariff` | Stores the exact approved tariff selected when the order is confirmed. |
| `confirmed_pricing_basis` | Read-only selection | Frozen charging basis: per service, tug, hour, tug-hour, day, or quotation. |
| `confirmed_unit_rate` | Read-only monetary | Frozen tariff rate used for final billing. |
| `confirmed_minimum_charge` | Read-only monetary | Frozen floor applied to the calculated base amount. |
| `confirmed_currency_id` | Read-only many-to-one to `res.currency` | Currency for frozen pricing, computed billable amounts, adjustments, and the invoice. Demo data uses PHP. |
| `pricing_frozen_at` | Read-only datetime | Audit timestamp showing when confirmed pricing was captured. |
| `confirmed_service_date` | Read-only date | Requested service date captured at confirmation for tariff-validity auditing. |
| `confirmed_service_date_changed` | Computed, stored boolean | Flags a date change after confirmation and forces a pricing exception instead of automatic billing. |
| `billing_reviewed_by_id` | Read-only many-to-one to `res.users` | Records the Billing Officer who completed review. |
| `billing_reviewed_at` | Read-only datetime | Records when billing review was completed; required before invoice creation. |
| `automated_completion_handoff` | Computed, stored boolean | Becomes true only when the Service Order is completed, exactly one active Marine Operation is completed, and every active Tug Completion is submitted. It is Finance's eligibility boundary. |
| `billing_note` | Text | Finance-only review note for exceptions or supporting context. |
| `billing_adjustment_ids` | One-to-many to `sedar.marine.billing.adjustment` | Holds explained charges and deductions included in the invoice. |
| `actual_billable_quantity` | Computed, stored float | Quantity derived from submitted tug actual start/end times according to the frozen pricing basis. |
| `base_billable_amount` | Computed, stored monetary | Frozen unit rate multiplied by actual quantity, subject to the minimum charge. |
| `adjustment_amount` | Computed, stored monetary | Signed total of all billing adjustments. |
| `total_billable_amount` | Computed, stored monetary | Base amount plus adjustments; cannot be negative when billing review is completed. |
| `invoice_ids` | One-to-many to `account.move` | Lists standard Odoo invoices linked to the Service Order. |
| `invoice_count` | Computed, stored integer | Counts linked customer invoices, including cancelled invoices for audit visibility. |
| `billing_status` | Computed, stored selection | Derives `not_ready`, `review`, `pricing_exception`, `draft_invoice`, `invoiced`, `partial`, `paid`, or `cancelled` from completion, pricing, invoice, and payment state. |

Key behavior:

- `action_confirm()` calls `_freeze_pricing()` so later tariff edits cannot silently change the agreed commercial basis.
- `_find_tariff()` requires an approved, effective-dated tariff matching client, service, port, terminal, and optional tug class.
- `_compute_final_billing()` uses actual submitted tug times. Per-tug-hour billing sums each tug's duration; per-hour billing uses the earliest actual start through the latest actual end.
- `action_mark_billing_reviewed()` requires the automated completion handoff and a non-negative result.
- `action_create_draft_invoice()` creates a draft customer invoice in standard Odoo Accounting and adds the base service plus each adjustment as invoice lines.
- `_compute_billing_status()` reflects standard `account.move` posting and payment state rather than maintaining a separate ledger.
- Billing Officers review existing Service Orders. They may update `billing_note` and maintain separate billing-adjustment records, but cannot create Service Orders or directly edit operational Service Order fields.

## `sedar.marine.operation` integration behavior

The dispatch record inherits the Service Order company as described above. Its lifecycle contract also changed materially:

- Its Service Order link is immutable after creation so the company, tug, crew, log, and delay snapshot cannot be reparented inconsistently.
- Tug Assignments, Manning Requirements, Crew Assignments, and Crew Shortages cannot be reparented after creation, and Operation Tug snapshot links are immutable. Corrections replace planning records instead of mutating the ownership chain beneath dispatch or manpower evidence.
- The system creates exactly one operation for a Ready Service Order with state `awaiting_start`.
- The earliest participating Tug Master's `actual_start` moves the operation and order to `in_progress` and becomes the operation's `actual_start`.
- When every active Tug Completion is submitted, the latest tug `actual_end` becomes the operation's `actual_end`; the operation and order become `completed` automatically.
- Returning a Tug Completion clears the operation end and reopens the operation and order.
- Manual Dispatch, Start, Complete, and Mark Billing Ready actions no longer control the lifecycle. The Dispatcher is an automated readiness function rather than a human approval role.
- Planning fields remain locked after readiness, while authorized Tug Completion fields remain writable through their protected workflow.

## `sedar.client.tariff`

This extends the existing client tariff so Finance can prove which authorized tariff applied at confirmation time.

| Field | Type | How it is used |
| --- | --- | --- |
| `terminal_id` | Many-to-one to `sedar.marine.berth` | Makes a tariff specific to a terminal within its port. |
| `approval_state` | Selection | Tracks `draft`, `approved`, or `superseded`. |
| `approved_by_id` | Read-only many-to-one to `res.users` | Audit identity of the Accounting Manager who approved it. |
| `approved_at` | Read-only datetime | Audit timestamp of approval. |
| `approval_reference` | Character | Stores the President authorization or equivalent business approval reference. |
| `approval_attachment` | Attachment-backed binary | Stores approval evidence when a textual reference is insufficient. |
| `approval_attachment_filename` | Character | Preserves the approval-evidence filename. |
| `previous_version_id` | Read-only many-to-one to the same model | Links a revision to the tariff version it replaces. |
| `revision_ids` | One-to-many to the same model | Displays the forward revision history. |

Only the Accounting Manager may create, approve, revise, edit, or delete governed tariff data. Approval requires a port, terminal, and authorization evidence. Approved versions are immutable; a changed rate or commercial rule requires an effective-dated revision. Approved or superseded history cannot be deleted.

## `sedar.marine.billing.adjustment`

This is the only new persistent model introduced by the finance MVP. One record is a separately explained addition to or deduction from a Service Order's base charge.

| Field | Type | How it is used |
| --- | --- | --- |
| `sequence` | Integer | Controls adjustment display and invoice-line order. |
| `order_id` | Required many-to-one to `sedar.marine.service.order` | Parent billing review; deleting the order cascades to its adjustments. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the Service Order and enforced by a global allowed-company record rule. |
| `description` | Required character | Short customer-facing label placed on the invoice line. |
| `adjustment_type` | Required selection | Chooses a positive `charge` or negative `deduction`. |
| `quantity` | Required float | Number of units; must be positive. |
| `unit_rate` | Required monetary | Rate per adjustment unit; cannot be negative because the type controls the sign. |
| `currency_id` | Related, stored many-to-one to `res.currency` | Uses the parent order's confirmed currency. |
| `amount` | Computed, stored monetary | Signed `quantity × unit_rate`, negative for deductions. |
| `reason` | Required text | Documents why Finance applied the adjustment and is included in the invoice-line description. |

Only a Billing Officer may maintain adjustments. They are locked while the order has a non-cancelled invoice, preventing the billing review from diverging from its invoice.

## `account.move`

The finance module extends Odoo's standard invoice model instead of creating a custom invoice or ledger.

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_service_order_id` | Indexed company-checked many-to-one to `sedar.marine.service.order` | Links a customer invoice to its originating Service Order. The source order must belong to the invoice company; the link is copied neither to duplicates nor removable while referenced by the invoice. |

Posting, taxes, receivables, payment registration, reconciliation, credit notes, and accounting reports remain standard Odoo Accounting behavior, as required by ADR-0001.

## `res.company` demo extension

No field is added. `sedar_configure_demo_currency()` changes the main demo company's currency to PHP and updates seeded service types, tariffs, working order currency, and frozen order currency. It is demo bootstrap behavior, not a replacement for normal company accounting configuration.

`sedar_recruitment_demo` also adds the method-only `sedar_ensure_recruitment_demo()` extension.
It creates and reconciles fictional HR users, portal ownership, recruitment applicants,
ADM-3 profile/supporting records, interviews, ADM-4 appraisal requests, ADM-5 requirement
requests, and one converted employee. The method is invoked by XML data during module install
and upgrade so the Slice 1 recruitment baseline is repeatable. It uses stable external IDs under
the `sedar_recruitment_demo` module and avoids deleting or replacing unrelated user-created
records.

`sedar_recruitment_crewing` adds the method-only `sedar_ensure_crew_onboarding_demo()` extension.
It reconciles a fictional marine crew onboarding case for the converted Chief Engineer demo hire
when the recruitment and service-order demo records are available. It is demo bootstrap behavior
only; it does not make recruitment the owner of crew deployment eligibility.

## `res.users` theme extension

No field is added. `sedar_set_default_home_action()` assigns the Marine Operations Service Order dashboard to the standard `action_id` field of every internal user. The theme bootstrap calls it so a fresh shared Docker installation opens on the team's custom dashboard instead of the stock Odoo home screen. If the dashboard action is unavailable, the method exits without changing users.

## `hr.recruitment.stage` applicant portal extension

The portal extension maps an internal Odoo Recruitment stage to the status and instructions an applicant is allowed to see.

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_public_status` | Selection | Maps the stage to one of the controlled applicant-visible statuses from received through successful or closed. |
| `sedar_public_title` | Character | Optional applicant-facing title for the stage. |
| `sedar_public_message` | Text | Default applicant-facing explanation of the stage. |
| `sedar_public_action_required` | Boolean | Indicates that the stage expects an applicant response or submission. |

## `hr.applicant` portal and recruitment extensions

The existing Odoo applicant remains the aggregate for one person's application. Portal ownership is separate from the applicant's contact record and every portal query checks that ownership before exposing an application, interview, or document.

### Portal and public-status fields

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_portal_partner_id` | Read-only many-to-one to `res.partner` | Verified owner allowed to access the application through the portal. |
| `sedar_claim_token` | Read-only unique character | Random, single-use activation token; regenerated by HR and cleared after a successful claim. |
| `sedar_claim_expires_at` | Read-only datetime | Limits activation-link validity to two days. |
| `sedar_portal_claimed_at` | Read-only datetime | Audit time of successful portal activation. |
| `sedar_claim_url` | Computed character | Builds the activation URL from the configured Odoo base URL and claim token. |
| `sedar_public_status` | Required tracked selection | Applicant-visible status independent of unrestricted internal notes. |
| `sedar_public_status_label` | Computed character | Display label for the controlled public status. |
| `sedar_public_message` | Tracked text | Status explanation shown to the applicant. |
| `sedar_status_updated_at` | Read-only datetime | Audit time of the most recent public-status change. |
| `sedar_action_required` | Tracked boolean | Signals that the applicant must respond or submit requirements. |
| `sedar_action_instructions` | Text | Applicant-facing instructions for the required action. |
| `sedar_portal_event_ids` | One-to-many to `sedar.applicant.portal.event` | Applicant-visible status timeline. |

Applicant creation generates a random activation token and initial timeline event. Portal activation refuses to reuse an internal user, creates or reactivates only a portal user, binds applications for the same contact, and clears the token. Portal access can be revoked by HR.

### HR processing fields

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_recruiter_assigned_at` | Read-only datetime | Records when an HR recruiter was assigned. |
| `sedar_review_deadline` | Tracked date | Internal target for completing the current review. |
| `sedar_next_action_date` | Tracked date | Due date for the next HR or applicant action. |
| `sedar_next_action` | Tracked character | Concise next action used by the processing dashboard. |
| `sedar_rejection_reason` | Tracked text | Required internal reason before the SEDAR rejection action may run. |
| `sedar_withdrawal_reason` | Tracked text | Records why an application was withdrawn. |
| `sedar_stage_history_ids` | One-to-many to `sedar.applicant.stage.history` | Auditable internal stage-change history. |
| `sedar_interview_ids` | One-to-many to `sedar.applicant.interview` | Interviews belonging to the application. |
| `sedar_requirement_request_ids` | One-to-many to `sedar.document.request` | Controlled applicant document requests, including ADM-5. |
| `sedar_offer_ids` | One-to-many to `sedar.applicant.offer` | Hiring decisions and offers belonging to the application. |
| `sedar_current_offer_id` | Computed many-to-one to `sedar.applicant.offer` | Exposes the active issued or accepted offer, if one exists. |
| `sedar_is_overdue` | Computed, searchable boolean | Identifies applications whose next-action date is before today. |

Workflow actions move applicants through controlled SEDAR stages, synchronize the public status, and create stage history. Interview completion requires a submitted ADM-4 appraisal. For marine crew applicants in the demonstration, ADM-4A Background Inquiry and CM-053 Company Interview Orientation are mandatory internal HR controls after interview completion. HR must issue an offer and the applicant must accept it before ADM-5 employment requirements may be requested. Employment-requirement verification requires an ADM-5 request to be submitted and approved. Employee conversion uses Odoo Recruitment's native employee creation and is blocked until both an accepted offer and the approved ADM-5 request exist. Conversion is idempotent: if a linked employee already exists, the action opens that employee rather than creating another one. A successful conversion writes recruitment source fields to the employee and synchronizes vacancy/manpower fulfillment, but it does not resolve the original operational crew shortage.

## `hr.employee` recruitment onboarding extension

The existing Odoo employee remains the HR master record. SEDAR adds only source and onboarding fields needed to prove where a demonstration hire came from and what generic onboarding state HR still owns.

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_source_applicant_id` | Read-only indexed many-to-one to `hr.applicant` | Links the employee to the application that created the employee profile. Used to prevent duplicate employee creation. |
| `sedar_source_vacancy_id` | Read-only indexed many-to-one to `sedar.job.vacancy` | Links the employee to the approved vacancy whose headcount demand the hire fulfills. |
| `sedar_source_offer_id` | Read-only many-to-one to `sedar.applicant.offer` | Links the employee to the accepted offer used for the conversion gate. |
| `sedar_source_requirement_request_id` | Read-only many-to-one to `sedar.document.request` | Links the employee to the approved ADM-5 employment requirements request. |
| `sedar_employment_type` | Read-only selection | Stores the demonstration employment type accepted in the offer: probationary, regular, project-based, or contract. |
| `sedar_planned_start_date` | Read-only date | Stores the proposed start date accepted in the offer. |
| `sedar_onboarding_state` | Selection | Tracks generic HR onboarding as pending, in progress, or done. It does not represent marine deployment eligibility. |
| `sedar_onboarding_owner_id` | Many-to-one to `res.users` | HR owner responsible for completing the generic onboarding checklist and scheduled activity. |
| `sedar_onboarding_started_at` | Read-only datetime | Audit timestamp written when HR starts SEDAR onboarding. |
| `sedar_onboarding_completed_at` | Read-only datetime | Audit timestamp written when HR completes SEDAR onboarding. |
| `sedar_onboarding_checklist` | Text | Demonstration checklist covering employee master data, manager/job setup, access/payroll preparation, and the later marine Crew Profile handoff. |
| `sedar_crew_onboarding_ids` | One-to-many to `sedar.crew.onboarding` | Read-only list of marine crew onboarding cases linked to this employee. Non-marine employees normally have none. |

These fields are written by `hr.applicant.action_sedar_create_employee_profile()` after the standard Odoo employee is created. Non-marine hires stop at this HR employee record. Marine readiness remains owned by the later Crew Profile onboarding workflow.
When the source applicant owns a portal account, conversion links the employee work contact to that same portal partner so the applicant dashboard can transition to the employee dashboard without creating a second identity. HR Recruitment Managers, not ordinary recruitment users, control onboarding start/completion actions. Conversion schedules a `SEDAR Employee Onboarding` activity for the onboarding owner.

When `sedar_recruitment_crewing` is installed, the applicant-to-employee conversion method is extended method-only: after the generic employee source links are written, a marine vacancy with `crew_rank_id` creates or reuses one `sedar.crew.onboarding` case. Non-marine hires do not receive a Crew Profile or crew onboarding case.

## `sedar.crew.onboarding`

One record controls the crewing-owned handoff from a successful marine hire to an existing `sedar.crew.profile`. It proves that an employee exists, but does not by itself make the person assignable to Service Orders.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Sequenced character | Crew onboarding reference generated from `sedar.crew.onboarding`. |
| `employee_id` | Required many-to-one to `hr.employee` | Employee being prepared for marine crew deployment. Unique per employee. |
| `applicant_id` | Stored related many-to-one to `hr.applicant` | Source application from the employee source fields. |
| `vacancy_id` | Stored related many-to-one to `sedar.job.vacancy` | Source marine vacancy from the employee source fields. |
| `manpower_request_line_id` | Stored related many-to-one to `sedar.manpower.request.line` | Approved manpower demand that created the vacancy. |
| `rank_id` | Required many-to-one to `sedar.crew.rank` | Marine rank being onboarded; must match the source vacancy rank when a vacancy exists. |
| `home_tugboat_id` | Many-to-one to `sedar.tugboat` | Crewing-selected home tugboat for the profile; required before deployment eligibility. |
| `crew_profile_id` | Read-only many-to-one to `sedar.crew.profile` | Existing or created Crew Profile controlled by this onboarding case. |
| `state` | Selection | Draft, in progress, blocked, deployment eligible, or cancelled. |
| `required_certificate_type_ids` | Many-to-many to `sedar.crew.certificate.type` | Required credentials and medical records, inherited from the manpower request line when available or derived from matching manning templates. |
| `missing_certificate_type_ids` | Computed, stored many-to-many to `sedar.crew.certificate.type` | Required certificates without a currently valid Crew Profile certificate. |
| `deployment_eligible` | Computed, stored boolean | True only when the Crew Profile exists, is active, has the correct rank, has a home tugboat, and has all required certificates valid as of today. |
| `blocker_summary` | Computed, stored character | Human-readable reason deployment eligibility is blocked. |
| `opened_by_id` | Read-only many-to-one to `res.users` | User who opened the case. |
| `opened_at` | Read-only datetime | Case creation timestamp. |
| `verified_by_id` | Read-only many-to-one to `res.users` | Crewing Manager who marked the profile deployment eligible. |
| `verified_at` | Read-only datetime | Deployment eligibility timestamp. |
| `notes` | Text | Internal crewing notes. |

Key behavior:

- `hr.applicant._sedar_apply_employee_onboarding_sources()` creates one onboarding case only for marine vacancies.
- `_sedar_get_or_create_from_employee()` is idempotent and returns no case for non-marine employees.
- `action_create_crew_profile()` creates or links the existing Crew Profile, sets the vacancy rank, assigns the home tugboat when provided, and keeps the profile unavailable until readiness is verified.
- `action_mark_deployment_eligible()` sets the case to blocked when rank, home tugboat, Crew Profile, or certificate requirements are missing. When all checks pass, it marks the case deployment eligible and changes the Crew Profile availability to available.
- Only `sedar_recruitment_crewing.group_crewing_manager` can start, create profile, mark eligible, or cancel onboarding. Internal users have read-only access for traceability.
- When `sedar_crew_compliance` is installed, deployment eligibility requires verified, unexpired required credentials and medical records. Renewal-requested, submitted, rejected, missing, or expired credentials remain blockers.
- Deployment eligibility does not close a Service Order crew shortage or create a dated crew assignment. Operations or Crewing must still assign the qualified Crew Profile to a concrete requirement.

## `sedar.crew.certificate` compliance extension

The existing crew credential and medical record remains owned by Marine Operations. Slice 7 extends it so Crewing can prove controlled evidence, track renewal state, and make verified evidence part of readiness.

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_document_request_id` | Read-only many-to-one to `sedar.document.request` | Links the credential or medical record to the controlled evidence request generated from the `CREW-CRED-EVIDENCE` document type. |
| `sedar_verification_state` | Selection | Evidence state: verified, renewal requested, submitted for review, or rejected. Existing/demo certificate records default to verified until a renewal request is opened. |
| `sedar_verified_by_id` | Read-only many-to-one to `res.users` | Crew Compliance Manager who verified the approved controlled evidence. |
| `sedar_verified_at` | Read-only datetime | Verification timestamp. |
| `sedar_renewal_requested_by_id` | Read-only many-to-one to `res.users` | Crew Compliance Manager who opened the renewal request. |
| `sedar_renewal_requested_at` | Read-only datetime | Renewal request timestamp. |
| `sedar_renewal_due_date` | Computed, stored date | Thirty days before expiry, used for renewal follow-up visibility. |
| `sedar_expiry_state` | Computed, stored selection | Valid, renewal due, or expired based on the expiry date. |
| `sedar_is_medical` | Computed, stored boolean | Identifies medical records from the certificate type code or name for medical-readiness filtering. |
| `sedar_reviewer_note` | Text | Crewing compliance review note, required before evidence is rejected. |

Key behavior:

- `action_sedar_request_renewal()` creates or reuses a controlled Document Request, pre-fills crew, certificate type, number, and validity dates, starts the request, and moves the credential to renewal requested.
- `action_sedar_sync_from_document()` copies approved request values back to the credential and updates evidence state from the Document Request workflow.
- `action_sedar_verify()` requires an approved controlled evidence request and then records verification user/time.
- `action_sedar_reject()` requires a reviewer note and marks the evidence rejected.
- Direct writes to compliance audit fields are restricted to `sedar_crew_compliance.group_crew_compliance_manager` or workflow context.
- `sedar.crew.assignment._compute_eligibility()` is overridden by method extension so Service Order crew readiness counts only verified, unexpired required credentials.
- `sedar.crew.onboarding._compute_deployment_status()` is overridden by method extension so a marine hire cannot become deployment eligible with missing, expired, or unverified required credentials.

## `sedar.crew.unavailability`

One record is a dated reason why a Crew Profile is unavailable for assignment. It gives Crewing a temporary resolution path for leave, medical, training, or similar blockers without creating permanent headcount demand.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Computed, stored character | Human-readable label combining Crew Profile and source. |
| `crew_profile_id` | Required many-to-one to `sedar.crew.profile` | Crew member whose availability is blocked. |
| `employee_id` | Stored related many-to-one to `hr.employee` | Employee linked through the Crew Profile. |
| `source` | Selection | Leave, medical restriction, training blocker, temporary unavailability, or other. |
| `leave_id` | Many-to-one to `hr.leave` | Standard Odoo Time Off record that created or updates the unavailability. |
| `shortage_id` | Many-to-one to `sedar.crew.shortage` | Operational shortage that caused the non-hiring action, when applicable. |
| `action_id` | Many-to-one to `sedar.crew.shortage.action` | Resolution action that created the medical or training blocker, when applicable. |
| `date_start` | Required datetime | Start of the unavailable period. |
| `date_end` | Datetime | End of the unavailable period; empty represents an open-ended blocker for the demo. |
| `state` | Selection | Planned, active, done, or cancelled. Planned and active records block overlapping crew assignments. |
| `reason` | Required character | Short operational reason displayed in readiness explanations. |
| `notes` | Text | Internal Crewing context. |

Key behavior:

- `hr.leave` is extended method-only with `sedar_crew_unavailability_id`; approved Time Off for an employee with a Crew Profile creates or updates a leave-sourced unavailability record, while cancelled/non-approved leave cancels the linked blocker.
- `sedar.crew.profile` is extended with `unavailability_ids`.
- `sedar.crew.assignment._compute_eligibility()` is overridden by method extension so Service Order crew readiness checks dated leave, medical, training, temporary blockers, verified credentials, rank, availability status, and overlapping assignments together.

## `sedar.crew.shortage.action` availability extension

The existing shortage action remains the action log for operational shortage resolution. Slice 8 extends it so non-hiring actions can produce availability facts and temporary relief can create the concrete replacement assignment required by ADR-0003.

| Field | Type | How it is used |
| --- | --- | --- |
| `company_id` | Stored indexed related many-to-one to `res.company` | Company inherited from the operational crew shortage and enforced by a global allowed-company record rule. |
| `assigned_employee_id` | Company-checked many-to-one to `hr.employee` | Employee responsible for the resolution action; the employee must belong to the shortage company. |
| `action_type` | Selection extension | Adds `temporary_reliever` alongside existing replacement, reschedule, certificate, medical, training, and manpower actions. |
| `relief_crew_profile_id` | Many-to-one to `sedar.crew.profile` | Candidate relief crew for a temporary reliever action. |
| `relief_assignment_id` | Read-only company-checked many-to-one to `sedar.crew.assignment` | Concrete Service Order crew assignment created after the relief candidate passes eligibility checks; it must belong to the shortage company. |
| `unavailability_id` | Read-only many-to-one to `sedar.crew.unavailability` | Medical or training blocker created from the action. |
| `unavailability_start` | Datetime | Start date/time used for medical or training unavailability created from the action. |
| `unavailability_end` | Datetime | Optional end date/time for the medical or training blocker. |
| `unavailability_reason` | Character | Reason copied into the generated unavailability record. |

Key behavior:

- Starting a medical or training action can create a dated unavailability record for the assigned employee's Crew Profile.
- Completing a temporary reliever action requires an outcome, a relief Crew Profile, matching rank, and an eligible assignment under the existing readiness rules.
- Temporary relief resolves only the affected `sedar.crew.shortage` and does not change vacancy or manpower fulfillment.

## `sedar.crew.assignment` scheduling extension

The existing Service Order Crew Assignment remains the transactional source for who is planned or confirmed against a manning requirement. Slice 9 adds scheduling fields and actions so Operations and Crewing can use the same record in list and calendar views.

| Field | Type | How it is used |
| --- | --- | --- |
| `planned_start` | Stored related datetime | Mirrors the parent Service Order requested start for calendar and conflict views. |
| `planned_end` | Stored related datetime | Mirrors the parent Service Order requested completion for calendar and conflict views. |
| `scheduling_status` | Computed, stored selection | Eligible, blocked, or rejected, derived from assignment state and existing readiness eligibility. |
| `replacement_candidate_ids` | Computed many-to-many to `sedar.crew.profile` | Decision-support list of compatible available replacement profiles. It is not an automatic assignment. |

Key behavior:

- `action_confirm_assignment()` confirms only eligible crew assignments. Rank mismatch, missing or unverified credentials, dated unavailability, and overlapping assignments block confirmation with the existing eligibility reason.
- `action_reject_assignment()` marks a planned or blocked assignment rejected and triggers Service Order readiness reevaluation.
- Writing `state = confirmed` is protected by the same eligibility check, so UI bypasses cannot confirm an ineligible schedule.
- Updating crew or assignment state triggers the automated readiness sync instead of introducing a human dispatch approval.

## `sedar.crew.rotation`

One record represents a planned or active crew rotation period on a tugboat. It is a scheduling aid and does not replace the Service Order Crew Assignment truth used by the Dispatch Readiness Gate.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Computed, stored character | Crew/tugboat label for list and calendar views. |
| `crew_profile_id` | Required many-to-one to `sedar.crew.profile` | Crew member assigned to the rotation period. |
| `employee_id` | Stored related many-to-one to `hr.employee` | Employee behind the Crew Profile. |
| `tugboat_id` | Required many-to-one to `sedar.tugboat` | Tugboat or home vessel for the rotation period. |
| `rank_id` | Stored related many-to-one to `sedar.crew.rank` | Crew rank for filtering and coverage review. |
| `date_start` | Required datetime | Rotation start. |
| `date_end` | Required datetime | Rotation end. |
| `watch` | Selection | Day watch, night watch, standby, or unassigned for the demonstration. |
| `relief_crew_profile_id` | Many-to-one to `sedar.crew.profile` | Planned relief crew member, when known. |
| `handover_date` | Datetime | Planned handover point inside the rotation period. |
| `state` | Selection | Draft, planned, active, completed, or cancelled. |
| `notes` | Text | Internal scheduling notes. |

Key behavior:

- Rotation end must be later than start.
- Handover date must fall inside the rotation period.
- Planned or active rotations for the same Crew Profile cannot overlap.
- Rotation workflow actions move draft to planned, planned to active, active to completed, or cancel any unfinished rotation.

## Technical Maintenance Foundation

Slice 10 adds `sedar_marine_maintenance`, a focused integration addon on top of standard Odoo Maintenance. Standard `maintenance.equipment` and `maintenance.request` remain the work-order/equipment foundation. SEDAR fields add marine relationships and availability rules needed by the Dispatch Readiness Gate.

### `sedar.tugboat` maintenance extension

| Field | Type | How it is used |
| --- | --- | --- |
| `maintenance_equipment_ids` | One-to-many to `maintenance.equipment` | Lists marine equipment installed on the tugboat. |
| `maintenance_request_ids` | One-to-many to `maintenance.request` | Lists maintenance work orders affecting the tugboat. |
| `drydock_plan_ids` | One-to-many to `sedar.drydock.plan` | Lists dry-dock plans for the tugboat. |
| `open_maintenance_blocker_count` | Computed, stored integer | Counts open blocking work orders and active blocking dry-dock plans. |
| `maintenance_readiness_reason` | Computed, stored character | Summarizes the first blocking technical records for operational readiness visibility. |

Key behavior:

- `_sedar_sync_maintenance_availability()` sets `availability_status` to `maintenance` when blocking technical records exist.
- The same method restores `availability_status` to `available` only when no blocking maintenance request or dry-dock plan remains.
- Existing Service Order readiness continues to consume `sedar.tugboat.availability_status`; Maintenance becomes the source that controls the maintenance hold.

### `maintenance.equipment` marine extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_tugboat_id` | Many-to-one to `sedar.tugboat` | Identifies the tugboat carrying the equipment. |
| `sedar_parent_equipment_id` | Many-to-one to `maintenance.equipment` | Allows a marine equipment hierarchy such as tugboat, engine, pump, or subsystem. |
| `sedar_child_equipment_ids` | One-to-many to `maintenance.equipment` | Shows child equipment records. |
| `sedar_system` | Selection | Demonstration system grouping: propulsion, electrical, navigation, hull, deck machinery, safety, auxiliary, or other. |
| `sedar_criticality` | Selection | Critical, major, or minor equipment criticality for maintenance prioritization. |
| `sedar_installation_date` | Date | Installation date when known. |
| `sedar_running_interval_hours` | Float | Running-hour interval measured from the last verified planned-service reading. |
| `sedar_running_hour_reading_ids` | One-to-many to `sedar.equipment.running.hour.reading` | Immutable audit history of cumulative Equipment meter observations. |
| `sedar_current_running_hour_reading_id` | Computed, stored many-to-one | Latest valid observation and source of current Running Hours. |
| `sedar_current_running_hours` | Computed, stored float | Cumulative hours from the latest valid Running Hour Reading. |
| `sedar_verified_service_reading_id` | Read-only many-to-one | Manager-verified valid reading that established the current planned-service cycle. |
| `sedar_verified_service_work_order_id` | Read-only many-to-one | Completed planned work order that established the current service baseline. |
| `sedar_last_service_date` | Read-only date | Date derived from the verified service reading; legacy values do not establish a verified baseline. |
| `sedar_last_service_hours` | Read-only float | Hours derived from the verified service reading; legacy values do not establish a verified baseline. |
| `sedar_next_service_hours` | Computed, stored float | Verified baseline hours plus planned interval. |
| `sedar_remaining_service_hours` | Computed, stored float | Signed hours to the threshold: positive before due and negative when overdue. |
| `sedar_service_due_state` | Computed, stored selection | Unconfigured, not due, due at the exact threshold, or overdue. |
| `sedar_service_cycle_key` | Computed, stored character | Stable baseline-and-threshold identity used for alert deduplication. |
| `sedar_alerted_service_cycle_key` | Read-only character | Persists the service cycle already notified, including after the activity is completed. |
| `sedar_due_alert_assignment_state` | Computed selection | Shows whether a due alert is assigned or needs an explicit technician/fallback user. |
| `sedar_inventory_product_id` | Read-only company-checked many-to-one to `product.product` | Immutable originating Replacement Equipment Item Type created only by controlled installation. |
| `sedar_inventory_lot_id` | Read-only company-checked many-to-one to `stock.lot` | Immutable originating serial; product and serial identify at most one persistent Equipment record. |
| `sedar_inventory_current_lifecycle_id` | Read-only company-checked many-to-one to `sedar.inventory.lifecycle` | Open lifecycle currently installing this Equipment; cleared on technical uninstall without deleting Equipment or Running Hour history. |

Key behavior:

- Current Running Hours come only from the latest valid historical reading; Actual Service Time never changes the meter.
- A verified baseline requires a completed planned-maintenance work order and a valid reading for the same Equipment.
- Exact threshold creates one Odoo activity for the active Equipment technician or the explicitly configured company fallback. No arbitrary team member is selected.
- The Equipment row is locked while reconciling an alert, and the persisted service-cycle key prevents duplicate activities after completion or concurrent recomputation.
- Running-hour due status does not create a Purchase Request or change tugboat availability.

### `sedar.equipment.running.hour.reading`

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Computed, stored character | Human-readable Equipment, hours, timestamp, and superseded status used wherever a reading is referenced. |
| `equipment_id` | Required many-to-one to `maintenance.equipment` | Equipment whose cumulative meter was observed. |
| `company_id` | Stored related many-to-one | Company used for multi-company record rules. |
| `running_hours` | Required float | Non-negative cumulative hour-meter value. |
| `reading_at` | Required datetime | Observation time; duplicate and future timestamps are rejected. |
| `recorded_by_id` | Read-only many-to-one to `res.users` | Actual creating user, enforced server-side. |
| `notes` | Text | Optional observation context. |
| `evidence_attachment_ids` | Many-to-many to `ir.attachment` | Optional meter photo or other evidence. |
| `state` | Read-only selection | Valid or superseded. |
| `supersedes_reading_id` | Read-only many-to-one to the same model | Original valid reading replaced by this manager correction. |
| `superseded_by_reading_ids` | Read-only one-to-many | Direct correction created for this reading; at most one is allowed. |
| `correction_reason` | Read-only text | Mandatory explanation on a correction. |
| `superseded_by_id` | Read-only many-to-one to `res.users` | Manager who superseded the original reading. |
| `superseded_at` | Read-only datetime | Correction audit timestamp. |

Maintenance Users may create readings but cannot edit or delete them. Only Maintenance Managers may create a correction. Chronology validation checks both neighboring valid readings; a meter replacement requires a new Equipment identity.

### `maintenance.request` marine extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_tugboat_id` | Company-checked many-to-one to `sedar.tugboat` | Affected tugboat. Defaults from linked marine equipment when available. |
| `sedar_work_order_type` | Selection | Planned maintenance, defect/corrective, or dry-dock work. |
| `sedar_priority` | Selection | Low, medium, high, or critical marine priority. |
| `sedar_defect_source` | Character | Source of a corrective defect report. Required for defect work orders. |
| `sedar_availability_impact` | Selection | No impact, monitor only, or blocks tug readiness. |
| `sedar_blocks_tug_readiness` | Computed, stored boolean | True when availability impact is blocking and the work order is not closed. |
| `sedar_drydock_plan_id` | Company-checked many-to-one to `sedar.drydock.plan` | Optional dry-dock plan that owns or groups the work order. |
| `sedar_spare_part_note` | Text | Legacy placeholder retained for historical Slice 10 records; Slice 11 uses structured spare-part lines. |
| `sedar_part_line_ids` | One-to-many to `sedar.maintenance.part.line` | Spare parts requested, reserved, issued, and consumed for the work order. |
| `sedar_parts_status` | Computed, stored selection | Summarizes whether the work order has no parts, shortage, reserved, issued, or consumed parts. |
| `sedar_running_hours_at_service` | Float | Running-hour reading at service verification. |
| `sedar_service_reading_id` | Many-to-one to `sedar.equipment.running.hour.reading` | Valid reading selected for a completed planned-maintenance baseline. |
| `sedar_service_baseline_verified_by_id` | Read-only many-to-one to `res.users` | Maintenance Manager who verified the baseline. |
| `sedar_service_baseline_verified_at` | Read-only datetime | Baseline verification audit time. |
| `sedar_stage_done` | Related boolean | Exposes the standard Maintenance stage's done state for completion gating and UI visibility. |
| `sedar_closure_note` | Text | Required verification note before releasing a blocking work order. |
| `sedar_released_by_id` | Read-only many-to-one to `res.users` | Marine Maintenance Manager who released the tug from the work-order hold. |
| `sedar_released_at` | Read-only datetime | Release timestamp. |

Key behavior:

- Blocking work orders require an affected tugboat.
- Defect work orders require a defect source.
- `action_sedar_mark_blocking()` is restricted to Marine Maintenance Managers and places the affected tugboat on maintenance hold.
- `action_sedar_release_tug()` is restricted to Marine Maintenance Managers, requires a closure note, closes the work order if needed, records release audit fields, and restores the tug only when no other technical blocker remains.
- `action_sedar_verify_service_baseline()` is restricted to Marine Maintenance Managers and accepts only completed planned work, a valid same-Equipment reading, and no regression behind a newer verified service.

### `res.company` Maintenance extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_maintenance_fallback_user_id` | Many-to-one to `res.users` | Explicit active internal company user who receives due-Equipment activities when no active technician is assigned. Exposed through Maintenance settings. |

### `sedar.drydock.plan`

One record represents a planned dry-dock event for one tugboat. It provides planning visibility without inventing SEDAR regulatory intervals.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required character | Dry-dock plan title. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the tugboat for global allowed-company isolation. |
| `tugboat_id` | Required company-checked many-to-one to `sedar.tugboat` | Tugboat affected by the dry dock. |
| `planned_start` | Required datetime | Planned start. |
| `planned_end` | Required datetime | Planned completion; must be later than start. |
| `yard_name` | Required character | Shipyard or repair facility for the plan. |
| `scope_summary` | Required text | Summary of planned dry-dock scope. |
| `state` | Selection | Draft, planned, in progress, completed, or cancelled. |
| `availability_impact` | Selection | No impact or blocks tug readiness. |
| `sedar_blocks_tug_readiness` | Computed, stored boolean | True for planned or in-progress blocking dry dock. |
| `milestone_ids` | One-to-many to `sedar.drydock.milestone` | Planned dry-dock milestone checklist. |
| `work_order_ids` | One-to-many to `maintenance.request` | Maintenance work orders grouped under the dry-dock plan. |
| `release_note` | Text | Required before completing a dry-dock plan. |
| `released_by_id` | Read-only many-to-one to `res.users` | Marine Maintenance Manager who completed release. |
| `released_at` | Read-only datetime | Release timestamp. |

Key behavior:

- Planned or in-progress blocking dry dock records place the tugboat on maintenance hold.
- Completion requires a release note and records release user/time.
- Cancelling or completing a dry dock reevaluates tug availability.

### `sedar.drydock.milestone`

| Field | Type | How it is used |
| --- | --- | --- |
| `plan_id` | Required company-checked many-to-one to `sedar.drydock.plan` | Parent dry-dock plan. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the dry-dock plan for global allowed-company isolation. |
| `sequence` | Integer | Milestone ordering. |
| `name` | Required character | Milestone description. |
| `planned_date` | Required datetime | Planned milestone date. |
| `actual_date` | Datetime | Actual completion date when recorded. |
| `responsible_id` | Many-to-one to `res.users` | Responsible user. |
| `state` | Selection | Pending, done, or cancelled. |
| `note` | Text | Internal milestone note. |

Access rules:

- Marine Maintenance Users can read and maintain marine equipment, maintenance requests, dry-dock plans, and milestones, but cannot delete them through normal access.
- Marine Maintenance Managers control technical release actions.
- Operations Managers can read dry-dock plans and milestones for readiness context.

## Marine Inventory Foundation

Slice 11 adds `sedar_marine_inventory`, a focused integration addon on top of standard Odoo Inventory. Standard `product.product`, `stock.location`, and `stock.quant` remain the product, location, and quantity foundation. SEDAR records add marine operating context so Service Orders, maintenance work orders, tugboats, and Marine Operations consume the same stock facts.

### `product.product` Inventory Check extension

One storable Odoo product represents an Item Type. Inventory Check exposes only products explicitly marked as SEDAR Inventory Items; Odoo stock quants and moves remain quantity truth.

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_inventory_item` | Boolean, indexed | Includes the product in the Inventory Check workspace. |
| `sedar_manufacturer_part_number` | Character, indexed | Searchable manufacturer-assigned reference kept separate from `default_code`, which is labeled SEDAR Item Code in this workspace. |
| `sedar_item_type` | Required indexed selection | Classifies the Item Type as fuel/lubricant, spare/consumable, or Replacement Equipment; it is immutable after the first stock transaction. Replacement Equipment must be serial-tracked. |
| `sedar_compatibility_scope` | Required selection | Marks an Item Type as fleet-wide or restricted to selected tugboats. |
| `sedar_compatible_tugboat_ids` | Many-to-many to `sedar.tugboat` | Explicit list required for restricted compatibility. |
| `sedar_reorder_point` | Float | Manually maintained low-stock threshold; cannot be negative. |
| `sedar_stock_location_id` | Computed many-to-one to `stock.location` | Company's configured default Storage location; displayed separately from aggregate company Storage totals. |
| `sedar_on_hand_qty` | Computed float | Physical quantity summed only across the company's explicitly tagged Storage locations. |
| `sedar_reserved_qty` | Computed float | Quantity reserved across those tagged Storage locations. |
| `sedar_available_to_issue` | Computed float | On Hand minus Reserved across those tagged Storage locations. The issue modal shows availability for the selected exact Storage location. |
| `sedar_stock_status` | Computed selection | In Stock, Low Stock, or Out of Stock from Available to Issue and Reorder Point. |
| `sedar_compatibility_display` | Computed character | Fleet-wide or a readable list of compatible tugboats. |
| `sedar_code_locked` | Computed boolean | Makes the SEDAR Item Code immutable after the first non-cancelled stock movement. |

Key behavior:

- The SEDAR Item Code (`default_code` in the Odoo product foundation) is required and unique among SEDAR Inventory Items.
- Restricted Item Types require at least one explicitly compatible tugboat.
- Storage includes only explicitly tagged Storage locations and excludes child, tug, consumption, and disposal locations.
- Procurement and Inventory Officers may create and maintain Item Types but cannot directly edit stock balances or change an Item Code after stock movement begins.

### `sedar.inventory.issue`

One record is the immutable audit fact for a controlled Inventory Issue. New issues move stock from an exact tagged Storage location to the selected tugboat's tagged location and create one open lifecycle. Pre-lifecycle issues remain unchanged and are explicitly identified as legacy one-step consumption history.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required read-only character | Sequence-generated reference using `SII/<year>/#####`. |
| `company_id` | Required immutable indexed many-to-one to `res.company` | Company derived from the selected Storage location and used for allowed-company isolation. |
| `product_id` | Required read-only company-checked many-to-one to `product.product` | Issued Item Type. |
| `manufacturer_part_number` | Read-only related character | Manufacturer reference visible in the audit record. |
| `tugboat_id` | Required read-only company-checked many-to-one to `sedar.tugboat` | Tugboat receiving the issued item. |
| `source_location_id` | Required read-only company-checked many-to-one to `stock.location` | Exact tagged Storage location reduced by the issue. |
| `tug_location_id` | Required read-only company-checked many-to-one to `stock.location` | Selected tugboat's tagged internal stock destination. |
| `quantity` | Required read-only float | Quantity issued; must be positive and no greater than Available to Issue. |
| `product_uom_id` | Read-only related many-to-one to `uom.uom` | Product unit of measure. |
| `purpose` | Required read-only text | Operational reason for the issue. |
| `issued_by_id` | Required read-only many-to-one to `res.users` | Procurement and Inventory Officer who confirmed the issue. |
| `issued_at` | Required read-only datetime | Confirmation time. |
| `stock_move_id` | Required read-only company-checked many-to-one to `stock.move` | Completed Odoo movement from Storage to tugboat stock. |
| `lot_id` | Read-only company-checked many-to-one to `stock.lot` | Selected lot or required Replacement Equipment serial. |
| `lifecycle_id` | Read-only company-checked many-to-one to `sedar.inventory.lifecycle` | Open/closed trace created for a new issue; absent on legacy one-step history. |
| `legacy_consumed` | Read-only boolean | Marks historical one-step issues whose done moves remain unchanged and do not invent onboard balances. |

Key behavior:

- The exact configured Procurement and Inventory Officer is enforced server-side; membership in the Officer group alone is insufficient.
- Issue to Tug hard-blocks incompatible tugboats, foreign or untagged locations, missing tug destinations, wrong serials, and insufficient reserved-aware availability.
- Completion atomically creates a standard done Storage-to-tug movement, immutable issue, and lifecycle. A failed movement rolls the domain facts back.
- Completed issues cannot be edited or deleted.

### `sedar.inventory.lifecycle`

One immutable lifecycle is the Currently In Use umbrella for a new Inventory Issue. Its stock quantity is derived from the issue move and append-only closing events, while `usage_state` supplies technical context.

| Field | Type | How it is used |
| --- | --- | --- |
| `name`, `issue_id` | Stored related name and required company-checked issue link | Preserve the immutable Inventory Issue identity; one issue has at most one lifecycle. |
| `company_id` | Required immutable indexed many-to-one | Company boundary for rules, stock, tugboat, Equipment, and exact Officer authority. |
| `product_id`, `item_type`, `product_uom_id` | Immutable product, related classification, and UoM | Identify the Item Type and rounding used by every quantity check. |
| `tugboat_id`, `source_location_id`, `tug_location_id` | Required immutable company-checked links | Preserve the tugboat and exact movement endpoints. |
| `issue_move_id`, `initial_qty` | Required immutable done move and quantity | Authoritative opening movement and issued quantity; endpoints, product, company, quantity, and lot must match. |
| `open_qty`, `state` | Computed stored float and selection | Initial quantity less done return/consume/dispose events, rounded by product UoM; state is open or closed. |
| `usage_state` | Controlled read-only selection | Onboard, assigned, installed, uninstalled (`removed` technical key), or closed technical context. |
| `lot_id`, `equipment_id` | Read-only company-checked links | Lot/serial and optional related Equipment. Open Replacement Equipment serials are unique. |
| `issued_by_id`, `issued_at` | Required immutable audit user/time | Actor and time from the Inventory Issue. |
| `installed_at`, `removed_at` | Computed stored datetimes | Latest install and technical-removal events. |
| `reconciliation_state` | Computed stored selection | Reconciled only when all linked moves are done and aggregate event-derived open quantity equals exact physical stock for the company/tug location/Item Type/lot bucket at UoM precision; otherwise Needs Review. All open lifecycles sharing a non-serialized bucket receive the same result. |
| `event_ids` | Read-only one-to-many | Append-only technical and disposition history. |
| `disposition_activity_id` | Read-only many-to-one to `mail.activity` | Deduplicated Officer task scheduled after technical uninstall and closed on final disposition. |
| `serial_open_key` | Computed stored character | Enforces one open lifecycle for a Replacement Equipment product/serial pair. |
| `is_procurement_inventory_officer` | Non-stored computed boolean | User-dependent UI helper; server actions independently enforce exact Officer authority. |

Maintenance Managers control assignment, Replacement Equipment installation, and technical uninstall. Uninstall clears the Equipment installation context but deliberately leaves the lifecycle open and its physical stock at the tug location; it creates no stock move because no stock-location boundary has changed, and it preserves Equipment identity and Running Hour history. The exact Officer later controls the distinct physical disposition step: partial return, consumption, or disposal. Every stock-closing action row-locks and reloads the lifecycle, rechecks rounded open quantity and unreserved physical stock, creates a standard done move to the configured destination, and appends its event in one transaction. Installed Replacement Equipment must be uninstalled before disposition and cannot be partially closed. Done stock moves crossing a tug location recompute reconciliation for the affected aggregate bucket so unlinked physical movements surface as Needs Review.

### `sedar.inventory.lifecycle.event`

| Field | Type | How it is used |
| --- | --- | --- |
| `lifecycle_id`, `company_id` | Required company-checked lifecycle and stored related company | Own and isolate the event. |
| `event_type` | Required read-only selection | Assign, install, technical uninstall (`remove` technical key), return, consume, or dispose. |
| `quantity`, `product_uom_id` | Read-only float and related UoM | Zero for technical events; positive for stock-closing events. |
| `stock_move_id` | Read-only company-checked many-to-one | Required done move for a closing event and forbidden for technical events. |
| `actor_id`, `event_at`, `reason` | Required actor/time and read-only reason | Attribution; disposition events require a reason. |

Lifecycle and event create/write/delete ACLs are read-only. Controlled actions elevate only their internal append after validating the real user, so caller-supplied RPC context cannot forge history.

### Inventory lifecycle wizards

`sedar.inventory.issue.wizard` exposes `company_id`, required `product_id`, related manufacturer part number and Item Type, a selectable same-company tagged `source_location_id`, computed exact-location `available_to_issue`, required company-checked `tugboat_id`, related read-only `tug_location_id`, `quantity`, related UoM, required `purpose`, and optional company-checked `lot_id`. Replacement Equipment makes the matching serial mandatory; the controlled issue action remains authoritative.

`sedar.inventory.disposition.wizard` is a transient modal with `lifecycle_id` (required company-checked many-to-one), related `company_id`, `product_id`, `tugboat_id`, `open_qty`, and `product_uom_id`, a read-only required `action` selection, and editable required `quantity` and `reason`. It invokes the selected return, consume, or dispose action; the lifecycle revalidates all authority and stock facts.

`sedar.inventory.technical.wizard` is a transient modal with `lifecycle_id` (required company-checked many-to-one), related `company_id`, `product_id`, and `tugboat_id`, a read-only required `action` selection, and optional company-checked `equipment_id`. Maintenance Managers use it to assign a spare/consumable to existing Equipment or to install/remove Replacement Equipment; server actions revalidate authority and lifecycle state.

### `res.company` and `stock.location` Inventory ownership

| Model and field | Type | How it is used |
| --- | --- | --- |
| `res.company.sedar_procurement_inventory_officer_id` | Many-to-one to `res.users` | Exact active internal company user who controls Procurement and stock disposition; owned by Inventory and exposed in Purchase settings. |
| `res.company.sedar_default_storage_location_id` | Many-to-one to `stock.location` | Default tagged Storage proposed for issue; multiple tagged Storage locations may still be selected. |
| `res.company.sedar_consumption_location_id` | Many-to-one to `stock.location` | Configured tagged inventory-loss destination for consumption. |
| `res.company.sedar_disposal_location_id` | Many-to-one to `stock.location` | Configured tagged inventory-loss destination for disposal. |
| `stock.location.sedar_location_role` | Indexed selection | Explicitly tags Storage, Tugboat Stock, Consumption, or Disposal. Storage/tug roles require internal locations; consumption/disposal require inventory-loss locations. |
| `stock.location.sedar_tugboat_id` | Indexed company-checked many-to-one to `sedar.tugboat` | Required and unique for a Tugboat Stock location; forbidden on every other role. |

`res.config.settings.sedar_default_storage_location_id`, `sedar_consumption_location_id`, and `sedar_disposal_location_id` are editable related many-to-one fields exposing the three company locations in standard Inventory settings. Upgrade migration tags only evidence-backed locations, configures a company default only when unambiguous, classifies old issues as legacy consumed, and never rewrites their moves or creates lifecycle balances from opening quants.

### `sedar.tugboat` inventory extension

| Field | Type | How it is used |
| --- | --- | --- |
| `stock_location_id` | Company-checked many-to-one to `stock.location` | Unique tagged Tugboat Stock location linked back to this same tugboat; represents onboard and installed goods. |

### `sedar.inventory.template`

One record defines the stock products normally required for one Service Order service type.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required character | Template label. |
| `company_id` | Stored related many-to-one to `res.company` | Company derived from the required source location and used for access isolation and Service Order template matching. |
| `service_type_id` | Required many-to-one to `sedar.marine.service.type` | Service type that triggers this requirement template. |
| `tug_class_id` | Many-to-one to `sedar.tug.class` | Optional tug-class-specific requirement rule. |
| `source_location_id` | Required company-checked many-to-one to `stock.location` | Company-owned internal stock location checked for available quantity. Shared locations are rejected because they do not establish deterministic template ownership. |
| `line_ids` | One-to-many to `sedar.inventory.template.line` | Products and quantities generated for matching Service Orders. |
| `active` | Boolean | Allows old demo templates to be retired without deleting history. |

Changing the source location revalidates every existing line against the new location company before ownership can change. Company-owned products cannot be stranded under a template from another company.

### `sedar.inventory.template.line`

| Field | Type | How it is used |
| --- | --- | --- |
| `template_id` | Required many-to-one to `sedar.inventory.template` | Parent template. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the Inventory Template for company checks and record rules. |
| `sequence` | Integer | Display order. |
| `product_id` | Required company-checked many-to-one to `product.product` | Shared product or company-owned stock product required by the Service Order. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `required_qty` | Required float | Base required quantity; must be greater than zero. |
| `per_tug` | Boolean | Multiplies the required quantity by `number_of_tugs` when generated. |

### `sedar.inventory.requirement`

One record is a stock-backed Service Order inventory requirement. It replaces the manual Inventory Readiness Confirmation whenever requirement lines exist.

| Field | Type | How it is used |
| --- | --- | --- |
| `order_id` | Required many-to-one to `sedar.marine.service.order` | Parent Service Order. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the Service Order for relationship checks and record rules. |
| `product_id` | Required company-checked many-to-one to `product.product` | Required stock product; it must be shared or belong to the Service Order company. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `source_location_id` | Required company-checked many-to-one to `stock.location` | Internal location checked for available quantity; a company-owned location must match the Service Order company. |
| `required_qty` | Required float | Required quantity; must be greater than zero. |
| `available_qty` | Computed, stored float | Available quantity from standard Odoo stock quants at the source location. |
| `shortage_qty` | Computed, stored float | Required quantity not currently available. |
| `readiness_state` | Computed, stored selection | `ready` or `shortage`; feeds the Dispatch Readiness Gate. |
| `auto_generated` | Boolean | Marks lines generated from a Service Order inventory template. |
| `note` | Text | Optional operational inventory note. |

Key behavior:

- `action_generate_inventory_requirements()` regenerates auto-generated requirement lines from the matching template for planned, blocked, or ready Service Orders.
- `_find_inventory_template()` selects only a template owned by the Service Order company; another company's template is never used as a fallback.
- `_sync_inventory_readiness()` writes the legacy `inventory_ready` flag from requirement-line availability only when requirement lines exist.
- `action_confirm_inventory_ready()` is blocked for orders with requirement lines because readiness is stock-derived.
- Service Order readiness shows `waiting_inventory` with a shortage summary when any requirement line is short.
- Once a Purchase Request line cites an Inventory Requirement, that requirement's Service Order, product, and source location are immutable so procurement evidence cannot drift from its operational source.

### `maintenance.request` inventory extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_part_line_ids` | One-to-many to `sedar.maintenance.part.line` | Work-order spare parts. |
| `sedar_parts_status` | Computed, stored selection | No parts, parts shortage, reserved, issued, or consumed. |

### `sedar.maintenance.part.line`

One record represents one spare-part product required by a maintenance work order.

| Field | Type | How it is used |
| --- | --- | --- |
| `maintenance_request_id` | Required many-to-one to `maintenance.request` | Parent work order. |
| `company_id` | Stored related indexed many-to-one to `res.company` | Company inherited from the work order for access and relationship checks. |
| `product_id` | Required company-checked many-to-one to `product.product` | Shared or same-company spare-part Item Type. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `source_location_id` | Required company-checked many-to-one to `stock.location` | Same-company tagged Storage used for the issue. |
| `requested_qty` | Required float | Required part quantity; must be greater than zero. |
| `available_qty` | Computed, stored float | Current available stock at the source location. |
| `reserved_qty` | Float | Quantity reserved for the work order in the demo control. |
| `legacy_issued_qty`, `legacy_consumed_qty` | Read-only floats | Upgrade-preserved counters for unlinked pre-lifecycle history. |
| `issued_qty` | Computed stored float | Legacy evidence plus initial quantities from linked lifecycles. |
| `consumed_qty` | Computed stored float | Legacy evidence plus done consume events from linked lifecycles. |
| `stock_move_ids` | Company-checked many-to-many to `stock.move` | Legacy and lifecycle issue/consumption movements for audit compatibility. |
| `lifecycle_ids` | Read-only company-checked many-to-many to `sedar.inventory.lifecycle` | New Storage-to-tug issues and their explicit disposition history. |
| `shortage_qty` | Computed, stored float | Quantity still short. |
| `state` | Computed, stored selection | Shortage, reserved, issued, or consumed. |
| `note` | Text | Optional maintenance inventory note. |

Key behavior:

- Reserve, issue, and consume actions enforce the work-order company's exact Procurement and Inventory Officer.
- Issuing routes the remaining requested quantity through the generic Storage-to-tug lifecycle entrypoint; repeat issue is rejected when the request is fully issued.
- Consumption closes only open linked lifecycle quantities through explicit tug-to-consumption moves; repeat consumption is rejected. Unlinked legacy records retain their original counters and moves.

### `sedar.marine.operation` inventory extension

| Field | Type | How it is used |
| --- | --- | --- |
| `fuel_log_ids` | One-to-many to `sedar.operation.fuel.log` | Fuel and lubricant logs for the operation. |
| `fuel_consumed_qty` | Computed, stored float | Sum of consumed fuel/lubricant quantities across operation logs. |

### `sedar.operation.fuel.log`

One record tracks fuel or lubricant issue and consumption for one tugboat in one Marine Operation.

| Field | Type | How it is used |
| --- | --- | --- |
| `operation_id` | Required many-to-one to `sedar.marine.operation` | Parent Marine Operation. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the Marine Operation for relationship checks and record rules. |
| `tugboat_id` | Required many-to-one to `sedar.tugboat` | Tugboat consuming fuel or lubricant. |
| `product_id` | Required company-checked many-to-one to `product.product` | Shared or same-company fuel or lubricant product. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `source_location_id` | Required company-checked many-to-one to `stock.location` | Internal source stock location; company-owned locations must match the operation company. |
| `tug_location_id` | Required company-checked many-to-one to `stock.location` | Tugboat onboard stock location; company-owned locations must match the operation company. |
| `opening_qty` | Float | Starting onboard quantity for the operation. |
| `quantity_to_issue`, `quantity_to_consume` | Editable floats | User inputs for the next controlled issue or consumption action; reset after success. |
| `legacy_issued_qty`, `legacy_consumed_qty` | Read-only floats | Upgrade-preserved pre-lifecycle counters. |
| `issued_qty` | Computed stored float | Legacy evidence plus quantities from linked lifecycle issues. |
| `consumed_qty` | Computed stored float | Legacy evidence plus linked done consumption events. |
| `stock_move_ids` | Company-checked many-to-many to `stock.move` | Auditable issue and consumption moves; every linked move must belong to the Marine Operation company. |
| `lifecycle_ids` | Read-only company-checked many-to-many to `sedar.inventory.lifecycle` | New lifecycle issues and explicit closing history for this fuel log. |
| `remaining_qty` | Computed, stored float | Opening plus issued minus consumed quantity. |
| `state` | Selection | Draft, issued, or consumption recorded. |
| `note` | Text | Optional operational fuel note. |

Key behavior:

- Issue and consumption actions enforce the Marine Operation company's exact Procurement and Inventory Officer.
- Issuing decreases source stock and increases tugboat stock using a standard move owned by the Marine Operation company, even when another company is active for the user.
- Recording consumption allocates the requested quantity oldest-first across open linked lifecycles, creates explicit tug-to-consumption moves, and updates the operation summary.
- Consumption cannot exceed open linked lifecycle quantity; repeated consumption after closure is rejected. Legacy opening/counter values remain history and are not converted into invented lifecycles.

Access rules:

- Inventory Check Users can read Inventory Check records, immutable issue history, same-company inventory templates, Service Order requirements, maintenance part lines, and operation fuel logs.
- Procurement and Inventory Officers may maintain Item Types and use controlled issue actions, but cannot directly edit stock balances or alter completed Inventory Issues.
- Operations Managers can read Service Order inventory requirements and operation fuel logs for dispatch and operational context.
- Marine Maintenance Users can read and maintain work-order spare-part lines for maintenance execution context.

## Procurement Handoff

`sedar_purchase_request` is a focused procurement-control addon on top of standard Odoo Purchase. SEDAR owns the confirmed internal need, internal review, supplier Bid capture, Line Awards, grouped draft-Purchase-Order handoff, procurement progress, and source traceability. Standard `purchase.order` confirmation, stock receipts, supplier bills, payments, and accounting entries remain owned by Odoo Purchase, Inventory, and Accounting under ADR-0007.

### `res.company` and Purchase settings

Inventory owns `res.company.sedar_procurement_inventory_officer_id` and validates that the configured employee is an active internal user allowed in the company with the Officer group. Procurement extends `res.company.write()` only to reconcile pending Purchase Request review activities when that setting changes. `res.config.settings.sedar_procurement_inventory_officer_id` remains an editable related field in standard Purchase settings, and the Purchase Request demo/configuration hook assigns the existing `procurement@sedar.demo` Demo Persona without changing the upgrade-stable user XMLID.

### `sedar.purchase.request`

One record is a department request to buy goods needed by maintenance, inventory, operations, or a manual business need.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Read-only character | Sequence-generated request number using `SPR/<year>/#####`. |
| `requester_id` | Required many-to-one to `res.users` | User requesting the purchase. |
| `department_id` | Many-to-one to `hr.department` | Optional requesting department. |
| `company_id` | Required many-to-one to `res.company` | Company context for the request, review assignment, and resulting Purchase Orders. |
| `currency_id` | Required many-to-one to `res.currency` | Currency for estimated request totals. |
| `vendor_id` | Legacy hidden many-to-one to `res.partner` | Preserved only so existing databases and linked procurement history remain upgrade-safe. New Purchase Requests do not select a preferred supplier. |
| `source_type` | Required selection | Maintenance, inventory, operations, or manual source classification. |
| `maintenance_request_id` | Many-to-one to `maintenance.request` | Optional work-order source for spare-part replenishment. |
| `service_order_id` | Company-checked many-to-one to `sedar.marine.service.order` | Optional Service Order source for operations or inventory replenishment; it must belong to the Purchase Request company. |
| `equipment_id` | Many-to-one to `maintenance.equipment` | Optional affected Equipment for an equipment-specific physical-goods need. When a maintenance work order identifies Equipment, the request must remain consistent with that source. |
| `required_date` | Required datetime | Date and time by which the requested goods are needed. |
| `priority` | Required selection | Normal, urgent, or emergency. |
| `justification` | Required text | Business reason for the purchase. |
| `line_ids` | One-to-many to `sedar.purchase.request.line` | Requested products, quantities, estimated costs, and source traceability. |
| `bid_ids` | Officer-only read-only one-to-many to `sedar.purchase.bid` | Supplier Bids captured for the approved request. The relation is hidden from ordinary requesters at field-access level. |
| `bid_count` | Officer-only computed, stored integer | Count used by the Bids smart button without exposing Bid identities or commercial values to requesters. |
| `purchase_order_ids` | Read-only one-to-many to `purchase.order` | All standard Purchase Orders linked to the request. One request may result in multiple orders when different suppliers win different lines. |
| `purchase_order_count` | Computed integer | Count used by the Purchase Orders smart button. |
| `purchase_order_id` | Legacy hidden many-to-one to `purchase.order` | Preserves the former single-order link for upgrade compatibility; it is included in the multi-order relationship during migration. |
| `purchase_order_state` | Legacy hidden related selection | Preserves the state of the former single-order link for upgrade compatibility. |
| `state` | Required selection | Internal request progress: draft, submitted, approved, order created, rejected, or cancelled. It remains separate from procurement progress. |
| `procurement_progress` | Computed selection | Procurement progress derived from internal state, active request lines, Line Awards, and linked downstream orders: not started, awaiting approval, ready for Bids, bidding, partially awarded, fully awarded, ordering, ordered, or cancelled. It is displayed separately from internal review progress. |
| `award_ids`, `award_count` | Officer-only one-to-many and computed integer | Opens the restricted immutable Line Award history without exposing commercial facts to ordinary requesters. |
| `legacy_handoff_recovery_required` | Computed boolean | Quarantines a legacy `po_created` request that no longer has a surviving linked order. |
| `handoff_recovery_reason`, `handoff_recovered_by_id`, `handoff_recovered_at` | Read-only audit fields | Preserve the Officer's explicit recovery of an incomplete legacy handoff back to approved procurement review. |
| `approved_by_id` | Read-only many-to-one to `res.users` | Procurement and Inventory Officer who approved the request. |
| `approved_at` | Read-only datetime | Approval timestamp. |
| `rejected_by_id` | Read-only many-to-one to `res.users` | Procurement and Inventory Officer who rejected the request. |
| `rejected_at` | Read-only datetime | Rejection timestamp. |
| `rejection_reason` | Text | Required explanation before rejection. |
| `is_procurement_inventory_officer` | Computed boolean | User-dependent form helper that exposes Officer-only controls only to the exact company-configured Officer; server actions still enforce the authority boundary. |
| `estimated_total` | Computed, stored monetary | Sum of all request-line estimated subtotals. |

Key behavior:

- `action_submit()` requires at least one request line and a configured company Officer, moves draft or rejected requests to submitted, and creates one deduplicated actionable review activity for that Officer.
- `action_approve()` and `action_reject()` enforce Procurement and Inventory Officer authority server-side. Approval does not require or select a supplier; rejection requires a reason and posts that reason to permanent chatter history before a corrected request may be resubmitted.
- Equipment-specific requests preserve a direct Equipment link in addition to any maintenance work-order source.
- `action_create_rfq()` remains only as an upgrade-safe legacy method and explains that Purchase Orders will be created from later Bid and Line Award workflow. It does not create an RFQ.
- `action_open_bids()` is Officer-only server-side and opens the request's Bid records with the request preselected for capture.
- The Purchase Orders smart button opens every linked standard order. Existing single-order history remains available after upgrade.
- Grouped Purchase Order creation requires every non-cancelled line to have an active Line Award, locks the request and lines, groups by exact winning Bid, and is idempotent through database source uniqueness.
- A legacy request-only Purchase Order is treated as an existing handoff and never causes synthetic Line Awards or duplicate orders.
- A legacy `po_created` request with no surviving order can return to approved only through the audited Officer recovery action.
- Internal request state and computed procurement progress are separate so procurement work cannot make the internal need appear unreviewed.
- Once Bid capture begins, the request company, currency, and line baseline are immutable. A request with Bid history cannot return to correction through rejection; received offers are withdrawn instead so commercial history is not erased.
- Service Order and inventory-requirement sources must belong to the Purchase Request company. Procurement consumes the ownership supplied by Marine Operations and Inventory rather than deriving a second company fact.
- The Purchase Request company is immutable after request lines, Bids, or Purchase Orders exist, including for elevated maintenance code. This keeps every stored related company and standard Purchase Order link consistent.

### `sedar.purchase.request.line`

One record is one requested product line under a Purchase Request.

| Field | Type | How it is used |
| --- | --- | --- |
| `request_id` | Required many-to-one to `sedar.purchase.request` | Parent Purchase Request; deleting the request cascades to its lines. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the parent request and indexed for company record rules. |
| `sequence` | Integer | Line display order. |
| `product_id` | Required many-to-one to `product.product` | Product to purchase. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure for the requested physical goods and later Purchase Order handoff. |
| `quantity` | Required float | Requested quantity; must be greater than zero. |
| `estimated_unit_price` | Monetary | Estimated supplier unit cost; cannot be negative. |
| `currency_id` | Related, stored many-to-one to `res.currency` | Currency inherited from the parent request. |
| `estimated_subtotal` | Computed, stored monetary | Quantity multiplied by estimated unit price. |
| `source_location_id` | Many-to-one to `stock.location` | Internal stock location whose shortage or replenishment need triggered the request. |
| `maintenance_part_line_id` | Many-to-one to `sedar.maintenance.part.line` | Optional maintenance spare-part shortage source. |
| `inventory_requirement_id` | Company-checked many-to-one to `sedar.inventory.requirement` | Optional Service Order inventory shortage source; its inherited company must match the Purchase Request company. |
| `need_reason` | Text | Optional line-specific explanation. |
| `bid_line_ids` | Officer-only read-only one-to-many to `sedar.purchase.bid.line` | Bid lines that quote this requested product; protected from ordinary requester reads at field-access level. |
| `line_state` | Read-only selection | Active or irreversibly cancelled. Only the exact Officer may cancel an approved line that has never been awarded or linked to a Purchase Order, through the controlled reason wizard. |
| `current_award_id` | Officer-only read-only many-to-one to `sedar.purchase.line.award` | Current active or ordered Line Award; reset clears this pointer but preserves history. |
| `award_history_ids` | Officer-only read-only one-to-many | Every award and reset event for this requested product. |
| `cancellation_reason`, `cancelled_by_id`, `cancelled_at` | Read-only audit fields | Preserve why an unawarded product was removed from the active order scope and who performed the irreversible action. |

Key behavior:

- Selecting a maintenance part line or inventory requirement populates product, quantity, and source location.
- A request line may reference either one maintenance part line or one inventory requirement, not both.
- The line validates physical goods only, positive quantity, non-negative estimated unit price, source-record consistency, and same-company products, locations, Service Orders, and inventory requirements.
- Request facts and lines become read-only after submission; a rejected request returns to an editable correction state only before Bid capture starts.
- Once any Bid exists, request lines cannot be added or deleted and their request assignment, product, quantity, and unit baseline cannot be changed.
- One active Line Award is enforced through a locked request line and a database-unique nullable active-line link. Reset is allowed only before any generated Purchase Order line has ever existed.
- Cancelling the final active line cancels the Purchase Request. A line with any award history, including a reset award, can never be cancelled. A changed need must be submitted as a new request rather than silently revising the approved baseline.

Access rules:

- Purchase Request Users can create, read, and update Purchase Requests and lines, but cannot delete them through normal access.
- Marine Inventory Users and Marine Maintenance Users can create, read, and update requests so stock and maintenance shortages can become procurement requests.
- The Procurement and Inventory Officer role implies Purchase Request User plus standard Odoo Purchase Manager and Inventory Manager authority. Its legacy `group_sedar_purchase_request_manager` XMLID remains unchanged only to preserve installed assignments and integrations.
- Ordinary Purchase Request Users do not inherit standard Odoo Purchase User authority.
- Global record rules restrict Purchase Requests and their lines to the user's allowed companies. Ordinary Purchase Request, Inventory, and Maintenance users can create and modify only requests where they are the requester; the Officer can manage all same-company requests.
- Bid headers, lines, prices, terms, and quotation files are accessible only to the exact Procurement and Inventory Officer configured for their company. Merely holding the underlying manager group does not grant commercial access. Allowed-company rules apply in addition to that exact-user rule.
- The controlled handoff creates draft standard `purchase.order` records. It does not confirm orders or create receipts, supplier bills, payments, or ledger entries.

### `sedar.purchase.bid`

One record preserves one Bidder's quotation for one approved Purchase Request. A request and Bidder pair is unique; a later lifecycle change never replaces the historical row.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Read-only character | Sequence-generated Bid reference using `SPB/<year>/#####`. |
| `request_id` | Required many-to-one to `sedar.purchase.request` | Approved Purchase Request being quoted; deleting the request is restricted. |
| `bidder_id` | Required many-to-one to `res.partner` | Canonical commercial supplier. It must have supplier standing and be shared or belong to the request company. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the Purchase Request and used by company and exact-Officer record rules. |
| `currency_id` | Stored related many-to-one to `res.currency` | MVP comparison currency inherited from the Purchase Request. Currency normalization is not performed. |
| `state` | Required read-only selection | Draft while captured, Received when validated into history, or Withdrawn when the supplier offer no longer applies. |
| `capture_source` | Required read-only selection | Manual Capture for new records or Legacy Conversion for a deterministic upgrade-created Bid. |
| `received_date` | Required date | Business date on which SEDAR received the supplier quotation. |
| `validity_date` | Date | Optional offer-expiry date; it cannot precede the received date. |
| `promised_delivery_date` | Date | Optional header delivery promise; it cannot precede the received date. |
| `delivery_terms` | Text | Supplier delivery terms applying to the Bid. |
| `availability_notes` | Text | Header-level availability information supplied by the Bidder. |
| `payment_terms` | Text | Supplier payment terms captured as quoted commercial text. |
| `warranty_notes` | Text | Warranty terms or limitations in the supplier offer. |
| `commercial_notes` | Text | Other Officer-only commercial context. |
| `quotation_file` | Attachment-backed binary | Private supplier quotation evidence. A manual Bid requires this file before receipt. |
| `quotation_filename` | Character | Original display filename for the private quotation. |
| `line_ids` | One-to-many to `sedar.purchase.bid.line` | Only the Purchase Request products this Bidder quoted; absence means not quoted. |
| `total_amount` | Computed, stored monetary | Currency-rounded sum of the quoted line subtotals. |
| `received_by_id`, `received_at` | Read-only user and datetime | Officer and server time recorded by the controlled receipt action. |
| `withdrawn_by_id`, `withdrawn_at` | Read-only user and datetime | Officer and server time recorded by the controlled withdrawal action. |
| `withdrawal_reason` | Text | Required explanation entered while Received and frozen when the Bid is withdrawn. |
| `award_ids` | Officer-only read-only one-to-many to `sedar.purchase.line.award` | Line Awards sourced from this Bid; any award history, including a reset award, permanently blocks Bid withdrawal. |

Key behavior:

- Only the exact company-configured Procurement and Inventory Officer may create, see, edit, receive, withdraw, or delete Bids. Direct RPC calls enforce the same authority as the views and record rules.
- Drafts may be edited and deleted. `action_receive()` requires at least one valid quoted line and, for manual capture, a quotation file; it alone records receipt audit fields. `action_withdraw()` requires a reason and it alone records withdrawal audit fields.
- Received and Withdrawn Bids, lines, commercial facts, quotation content, and audit metadata are immutable. Losing and unawarded offers therefore remain available as procurement history. A received Bid that has ever supplied a Line Award cannot later be withdrawn, even if that award was reset.
- The Bidder must be its canonical commercial partner. Duplicate request/Bidder records, non-suppliers, contacts, cross-company suppliers, and Bids against a non-approved request are rejected.
- Commercial values stay on the restricted Bid record and are not posted into the more broadly visible Purchase Request chatter.

### `sedar.purchase.bid.line`

One record is one requested product included in a supplier Bid. A Bid may cover any subset of the request, but each included line quotes the full requested quantity.

| Field | Type | How it is used |
| --- | --- | --- |
| `bid_id` | Required many-to-one to `sedar.purchase.bid` | Parent supplier Bid; deleting an editable Draft cascades to its lines. |
| `request_id` | Stored related many-to-one to `sedar.purchase.request` | Purchase Request inherited from the Bid for grouping and traceability. |
| `request_line_id` | Required many-to-one to `sedar.purchase.request.line` | Requested product being quoted; it must belong to the Bid's request and is unique within that Bid. |
| `company_id` | Stored related many-to-one to `res.company` | Company inherited from the Bid for access isolation. |
| `currency_id` | Stored related many-to-one to `res.currency` | Purchase Request currency inherited from the Bid. |
| `product_id` | Stored related many-to-one to `product.product` | Product snapshot supplied by the immutable requested-line relationship. |
| `product_uom_id` | Stored related many-to-one to `uom.uom` | Requested product unit used for full-quantity comparison and rounding. |
| `quantity` | Required read-only float | Server-copied snapshot of the full requested quantity; callers cannot override it. |
| `unit_price` | Required float with six decimal places | Non-negative supplier price per requested unit. |
| `subtotal` | Computed, stored monetary | Requested quantity multiplied by unit price and rounded in the Bid currency. |
| `availability_note` | Character | Product-specific availability statement. |
| `promised_delivery_date` | Date | Optional product-specific delivery promise not earlier than Bid receipt. |
| `delivery_terms` | Text | Product-specific delivery conditions. |
| `notes` | Text | Other product-specific quotation context. |
| `bidder_id`, `validity_date`, `warranty_notes` | Read-only related fields | Expose the Bid header's supplier, expiry, and warranty context in the restricted product-level comparison UI. |
| `award_display_name` | Computed character | Gives the award picker a meaningful restricted label containing Bidder, six-decimal price, validity, and delivery promise. |

Bid-line identity, quantity snapshots, and all commercial values are editable only while the parent Bid is Draft. The server rejects cross-request lines, duplicate lines, partial quantities outside the unit-of-measure rounding tolerance, negative prices, invalid delivery dates, and direct reassignment.

### `sedar.purchase.line.award`

One record is the immutable commercial decision for one Purchase Request product. Reset changes only its lifecycle and reset audit fields; it never overwrites or deletes the original winner facts.

| Field | Type | How it is used |
| --- | --- | --- |
| `request_id`, `request_line_id` | Required read-only many-to-one links | Purchase Request aggregate and exact requested product line represented by the decision. |
| `active_request_line_id` | Read-only nullable many-to-one with database uniqueness | Enforces at most one current award per request line; reset clears it while history remains. |
| `bid_id`, `bid_line_id`, `bidder_id` | Required read-only many-to-one snapshots | Received Bid, exact quoted line, and canonical winning supplier. |
| `company_id`, `currency_id`, `product_id`, `product_uom_id` | Required read-only snapshots | Ownership and product identity frozen when the award is recorded. |
| `quantity`, `unit_price` | Required read-only numeric snapshots | Full requested quantity and tax-exclusive six-decimal Bid price in the request UoM/currency. |
| `award_reason`, `awarded_by_id`, `awarded_at` | Required read-only audit fields | Best-value justification and exact Officer/server time. |
| `expired_bid_override`, `expired_bid_override_reason` | Read-only exception facts | Explicit approval and reason required when the Bid validity date has passed in the company-local business date. |
| `zero_price_confirmed` | Read-only boolean | Explicit confirmation required for a supplier quotation whose unit price rounds to zero at six decimals. |
| `state` | Read-only selection | Awarded, Reset, or Ordered. |
| `reset_reason`, `reset_by_id`, `reset_at` | Read-only audit fields | Mandatory controlled reset evidence, allowed only before order handoff. |
| `purchase_order_line_id` | Read-only many-to-one to `purchase.order.line` | Durable standard Purchase Order line created from this award. |

Awards are readable only by the exact Procurement and Inventory Officer configured for an allowed company. They cannot be created, edited, or deleted through normal model access; controlled wizards repeat exact-user validation and use internal elevated writes only after locking and revalidation. Purchase Request chatter receives neutral lifecycle notices and never copies Bidder, price, award reason, or other protected commercial facts.

### Procurement award wizards

The four transient models below collect only the decision input required by their corresponding controlled server action. They do not own durable business facts. Their ACLs allow the Procurement and Inventory Officer role to create short-lived wizard records, while each action still rechecks that the caller is the exact company-configured Officer, locks and reloads its durable target, and validates the current workflow state before storing durable audit facts.

#### `sedar.purchase.line.award.wizard`

| Field | Type | How it is used |
| --- | --- | --- |
| `request_line_id` | Required read-only many-to-one to `sedar.purchase.request.line` | Durable requested product selected from the Purchase Request row action. |
| `bid_line_id` | Required many-to-one to `sedar.purchase.bid.line` | Officer-selected received quote for the same request line; creation and opening from the picker are disabled. |
| `bidder_id`, `product_uom_id`, `currency_id` | Read-only related many-to-one fields | Supplier and unit/currency context for the selected quote. |
| `quantity`, `unit_price` | Read-only related floats | Full quoted request quantity and tax-exclusive six-decimal unit price. |
| `validity_date`, `promised_delivery_date` | Read-only related dates | Offer expiry and product-specific delivery promise. |
| `availability_note`, `warranty_notes` | Read-only related character/text | Availability and warranty context shown before confirmation. |
| `award_reason` | Required text | Manual best-value justification persisted on the immutable Line Award. |
| `expired_bid_override`, `expired_bid_override_reason` | Boolean and conditionally required text | Explicit exception and reason accepted only when the selected Bid is expired. |
| `zero_price_confirmed` | Boolean | Explicit confirmation required when the selected quote has a zero unit price. |

#### `sedar.purchase.line.award.reset.wizard`

| Field | Type | How it is used |
| --- | --- | --- |
| `award_id` | Required read-only many-to-one to `sedar.purchase.line.award` | Unordered active award being reset; the durable award remains as history. |
| `reason` | Required text | Reset rationale persisted with actor and server time on the award. |

#### `sedar.purchase.request.line.cancel.wizard`

| Field | Type | How it is used |
| --- | --- | --- |
| `request_line_id` | Required read-only many-to-one to `sedar.purchase.request.line` | Active approved requested product being removed from the handoff scope. It must never have been awarded or linked to a Purchase Order. |
| `reason` | Required text | Irreversible cancellation rationale persisted with actor and server time on the request line. |

#### `sedar.purchase.request.recovery.wizard`

| Field | Type | How it is used |
| --- | --- | --- |
| `request_id` | Required read-only many-to-one to `sedar.purchase.request` | Legacy `po_created` request whose historical Purchase Order link no longer survives. |
| `reason` | Required text | Recovery rationale persisted with actor and server time before returning the request to Approved. |

### `ir.attachment` Bid quotation behavior

The method-only extension recognizes attachments linked to `sedar.purchase.bid`. It validates both the existing and proposed parent on mutations, requires the exact company-configured Officer, prevents reassignment, and permits content changes or deletion only while the Bid is Draft. Bid attachments must remain private binary records: public access, URL attachments, and generated access tokens are rejected. Odoo's linked-record and field access checks protect attachment metadata and bytes from requesters and other unconfigured users, including direct attachment searches and reads.

### `purchase.order` procurement extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_purchase_request_id` | Read-only indexed many-to-one to `sedar.purchase.request` | Links one standard Purchase Order back to its originating Purchase Request. The relation supports multiple orders per request while Odoo Purchase continues to own the order lifecycle; only the controlled award workflow may set or change the link. |
| `sedar_bid_id` | Officer-only read-only indexed many-to-one to `sedar.purchase.bid` | Exact winning Bid grouped into this standard order. Request and Bid are database-unique together. |

Generated orders preserve partner, company, currency, and source identity. They may follow the standard confirmation, cancellation, receipt, supplier-bill, and Reset-to-Draft lifecycle, but cannot be deleted. A cancelled generated order remains award history and never causes an automatic replacement.
The winning Bid's escaped delivery, availability, payment, warranty, commercial, and awarded line-level terms are intentionally copied to the generated Purchase Order note so standard Odoo Purchase can execute the approved supplier agreement. The private quotation file, losing offers, and Purchase Request chatter remain restricted to the exact configured Officer.

### `purchase.order.line` procurement extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_purchase_request_line_id` | Read-only indexed many-to-one | Exact requested physical-goods line materialized by the standard order line. |
| `sedar_bid_line_id` | Officer-only read-only indexed many-to-one | Exact winning supplier quote used for price and delivery facts. |
| `sedar_line_award_id` | Officer-only read-only indexed unique many-to-one | Immutable Line Award that created the order line. |

Generated line product, request UoM, full quantity, and tax-exclusive award price are immutable. Odoo Purchase and Inventory continue to own taxes, planned arrival, confirmation, receipt, billing, and accounting lifecycle fields.

## HSSE and Operational Compliance

Slice 13 adds `sedar_hsse` as the authoritative demonstration addon for Health, Safety, Security, and Environment workflows. HSSE records link to Service Orders, Marine Operations, tugboats, terminals, crew profiles, employees, maintenance work orders, and controlled document requests without copying those master records.

### Shared source links

Incident, inspection, risk, permit, and meeting records share these optional source links: `service_order_id`, `operation_id`, `tugboat_id`, `berth_id`, `maintenance_request_id`, and `document_request_id`. Selecting a Marine Operation can populate the Service Order, and selecting a Service Order can populate the starting berth.

### `sedar.hsse.incident`

One record captures an incident, near miss, or unsafe condition.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Read-only character | Sequence-generated incident number. |
| `incident_type` | Required selection | Incident, near miss, or unsafe condition. |
| `category` | Required selection | People, vessel/equipment, environment, security, operation, or other. |
| `severity` | Required selection | Low, medium, high, or critical. |
| `occurrence_datetime` | Required datetime | When the event occurred. |
| `reported_by_id` | Required many-to-one to `res.users` | Reporter. |
| `investigator_id` | Many-to-one to `res.users` | HSSE investigator assigned by workflow. |
| `employee_ids` | Many-to-many to `hr.employee` | People involved. |
| `crew_profile_ids` | Many-to-many to `sedar.crew.profile` | Crew profiles involved. |
| `summary` | Required text | Initial report. |
| `immediate_action` | Text | Immediate containment or stop-work action. |
| `investigation_summary` | Text | Investigation result required before closure. |
| `root_cause` | Text | Root cause required before closure. |
| `confidential` | Boolean | Marks investigation content as confidential for later portal filtering. |
| `corrective_action_ids` | One-to-many to `sedar.hsse.corrective.action` | Follow-up actions linked to the incident. |
| `open_corrective_action_count` | Computed, stored integer | Unverified and uncancelled corrective actions. |
| `state` | Required selection | Reported, investigating, action required, verified closed, or cancelled. |
| `closed_by_id`, `closed_at`, `verified_by_id`, `verified_at` | Read-only audit fields | Closure and verification traceability. |

HSSE Managers control investigation start, action-required transition, cancellation, and verified closure. Verified closure requires investigation summary, root cause, and no open corrective actions.

### `sedar.hsse.inspection` and `sedar.hsse.inspection.finding`

An inspection record captures vessel, workplace, permit, PPE, environmental, or other inspections. Findings capture assigned owner, due date, severity, description, overdue state, and optional corrective action.

Important fields:

- `sedar.hsse.inspection.finding.is_overdue` is true when the due date has passed and the finding remains open or action-created.
- `sedar.hsse.inspection.overdue_finding_count` summarizes overdue findings for list views.
- `action_create_corrective_action()` creates one linked corrective action from a finding and preserves the assigned owner, due date, severity, and description.
- Inspection verification is blocked until every finding is closed or cancelled.

### `sedar.hsse.risk.assessment`

One record captures an activity hazard and approved control set.

Key fields include `activity`, `hazard`, `existing_controls`, `additional_controls`, `likelihood`, `impact`, computed `residual_risk_score`, computed `residual_risk_level`, `owner_id`, `approved_by_id`, `approved_at`, `corrective_action_ids`, and `state`. Likelihood and impact must be between 1 and 5. HSSE Managers approve risk assessments.

### `sedar.hsse.permit`

One record is a permit register entry.

Key fields include `permit_type`, `permit_number`, `issuing_authority`, `valid_from`, `valid_until`, `required_for_operations`, computed `is_expired`, computed `operational_exception`, computed `state`, source links, and `note`. An expired permit required for operations becomes an operational exception and is surfaced on linked Service Orders and tugboats.

### `sedar.hsse.corrective.action`

One record is an assigned corrective or preventive action linked to exactly one incident, inspection finding, or risk assessment. Safety meeting actions may also be linked to a meeting.

Key fields include `assigned_user_id`, `due_date`, `severity`, `critical_control`, `description`, `completion_note`, `evidence`, `completed_by_id`, `completed_at`, `verified_by_id`, `verified_at`, computed `is_overdue`, computed `operational_exception`, and `state`. Critical controls remain operational exceptions until verified or cancelled. Completion requires a completion note, and verification requires HSSE Manager authority.

### `sedar.hsse.meeting`

One record stores safety meetings, toolbox talks, or HSSE committee meetings. It records facilitator, attendees, topic, minutes, source links, and linked follow-up corrective actions.

### `sedar.hsse.training.record`

One record stores HSSE training completion for an employee and optional crew profile. It records course, type, completion date, optional expiry date, controlled document evidence, readiness applicability, computed expiry state, and note.

### Service Order and tugboat HSSE extensions

| Model | Field | Type | How it is used |
| --- | --- | --- | --- |
| `sedar.marine.service.order` | `hsse_exception_count` | Computed integer | Counts expired required permits and unresolved critical HSSE actions linked to the Service Order. |
| `sedar.marine.service.order` | `hsse_exception_summary` | Computed character | Human-readable summary of Service Order HSSE exceptions. |
| `sedar.tugboat` | `hsse_exception_count` | Computed integer | Counts expired required permits and unresolved critical HSSE actions linked to the tugboat. |
| `sedar.tugboat` | `hsse_exception_summary` | Computed character | Human-readable summary of tugboat HSSE exceptions. |

Access rules:

- HSSE Users can create, read, and update HSSE records but cannot delete them through normal access.
- HSSE Managers control investigation, risk approval, inspection verification, corrective-action verification, and cancellation actions.
- Portal-safe HSSE exposure is deferred; confidential investigation details are not exposed through a public route in this slice.

## `sedar.manpower.request` and `sedar.job.vacancy` fulfillment behavior

`sedar.manpower.request.line.company_id` is a stored, indexed relation to the parent Manpower Request company. The parent request, its lines, and crew-shortage resolution actions use global allowed-company record rules. `shortage_ids`, `job_id`, and `sedar.crew.shortage.manpower_request_line_id` are company-checked; the job is compatible when it is shared or belongs to the request company. The shortage's `crew_assignment_id` and computed `operation_id` are also company-checked and explicitly validated against the owning Service Order. The shortage action's `assigned_employee_id` must belong to the shortage company. The shortage-to-manpower workflow explicitly creates the request in the Service Order shortage company rather than whichever company is currently active for the user.

Once a Manpower Request has position lines, its company cannot change. Position lines and shortage-resolution actions also cannot be moved to another parent. These rules prevent existing shortage evidence, HR jobs, action history, and vacancy handoff records from silently inheriting a different owner.

Their fulfillment workflow contract also changed materially under ADR-0003:

- `sedar.manpower.request.action_open_vacancies()` creates or links vacancy records and moves the request to `position_open`; it no longer resolves linked operational crew shortages.
- `sedar.job.vacancy._sedar_sync_hiring_fulfillment()` derives the vacancy's `filled_openings` from employees whose `sedar_source_vacancy_id` points to that vacancy.
- A vacancy moves to `filled` and closes publication when filled openings meet approved openings.
- `sedar.manpower.request._sedar_sync_headcount_fulfillment()` closes the request only when all linked vacancies have no remaining openings.
- Linked `sedar.crew.shortage` records remain open/escalated until Operations or Crewing records a concrete operational resolution.

## `sedar.applicant.portal.event`

One event is a portal-safe milestone shown on an applicant's timeline. HR Recruitment users may read, create, and update events but may not delete them through normal access rights.

| Field | Type | How it is used |
| --- | --- | --- |
| `applicant_id` | Required many-to-one to `hr.applicant` | Parent application; deleting the application cascades to its events. |
| `event_type` | Required selection | Controlled public status category for the event. |
| `title` | Required character | Applicant-visible milestone title. |
| `message` | Text | Applicant-visible milestone explanation. |
| `occurred_at` | Required datetime | Event timestamp, defaulting to the current time. |
| `visible` | Boolean | Allows HR to suppress an event from the applicant timeline without deleting audit data. |

## `sedar.applicant.stage.history`

One record captures an internal applicant stage transition. HR Recruitment users may read, create, and update history but may not delete it through normal access rights.

| Field | Type | How it is used |
| --- | --- | --- |
| `applicant_id` | Required indexed many-to-one to `hr.applicant` | Parent application; deleting the application cascades to its history. |
| `previous_stage_id` | Many-to-one to `hr.recruitment.stage` | Stage before the transition; retained as empty when no previous stage exists. |
| `new_stage_id` | Required many-to-one to `hr.recruitment.stage` | Destination stage; deletion is restricted while referenced. |
| `changed_by` | Required many-to-one to `res.users` | User responsible for the change. |
| `changed_at` | Required datetime | Transition time. |
| `reason` | Text | Internal explanation or next-action context for the change. |
| `applicant_message` | Text | Snapshot of the applicant-facing message at transition time. |

## `sedar.applicant.interview`

One record coordinates one interview for an application. HR Recruitment users may read, create, and update interviews but may not delete them through normal access rights. Applicant portal routes use ownership checks and expose only confirmation or reschedule actions.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required character | Interview title used in Odoo and Calendar. |
| `applicant_id` | Required indexed many-to-one to `hr.applicant` | Parent application; deletion cascades to interviews. |
| `vacancy_id` | Stored related many-to-one to `sedar.job.vacancy` | Vacancy inherited from the application. |
| `job_id` | Stored related many-to-one to `hr.job` | Odoo job inherited from the application. |
| `interview_type` | Required selection | Initial, technical, or final interview. |
| `status` | Required tracked selection | Draft, scheduled, confirmed, completed, cancelled, no-show, or reschedule requested. |
| `start_datetime` | Required datetime | Scheduled start. |
| `end_datetime` | Required datetime | Scheduled end; validation requires it to be later than the start. |
| `location` | Character | Physical interview location. |
| `meeting_url` | Character | Optional online meeting link. |
| `coordinator_id` | Required many-to-one to `res.users` | HR owner coordinating the interview. |
| `interviewer_ids` | Many-to-many to `res.users` | Assigned interview panel. |
| `calendar_event_id` | Read-only many-to-one to `calendar.event` | Synchronized Odoo Calendar event. |
| `appraisal_request_id` | Read-only many-to-one to `sedar.document.request` | Generated ADM-4 appraisal request. |
| `applicant_confirmation_note` | Text | Applicant confirmation or reschedule explanation. |
| `result` | Selection | Recommended, conditional, not recommended, or pending. |
| `internal_notes` | Text | HR-only interview notes. |

Scheduling requires a qualified applicant and at least one interviewer, creates or updates the Calendar event, generates ADM-4, and moves the applicant to Interview Stage. Completing an interview is blocked until ADM-4 is at least submitted.

## `sedar.applicant.offer`

One record captures a hiring decision and offer version for one applicant. HR Recruitment users may read, create, and update offers but may not delete them through normal access rights. Applicant portal routes use ownership checks and expose only issued or accepted offers.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required character | Offer reference shown in HR views. |
| `applicant_id` | Required indexed many-to-one to `hr.applicant` | Parent application; deleting the application cascades to offers. |
| `vacancy_id` | Stored related many-to-one to `sedar.job.vacancy` | Vacancy inherited from the application. |
| `job_id` | Stored related many-to-one to `hr.job` | Odoo job inherited from the application. |
| `state` | Required selection | Draft, issued, accepted, declined, withdrawn, or expired. |
| `decision` | Required selection | Hire, conditional hire, or do not hire. Do-not-hire decisions must use the applicant rejection workflow rather than issuing an offer. |
| `decision_reason` | Text | Internal HR rationale, not rendered in the applicant portal. |
| `offered_position` | Required character | Applicant-visible offered role title. |
| `employment_type` | Required selection | Demonstration employment type: probationary, regular, project-based, or contract. |
| `proposed_start_date` | Required date | Applicant-visible target start date. |
| `expiry_date` | Required date | Applicant-visible response deadline; cannot be in the past when saved. |
| `offer_summary` | Required text | Applicant-visible summary of the offer terms used for the demo. |
| `issued_by_id` | Read-only many-to-one to `res.users` | HR user who issued the offer. |
| `issued_at` | Read-only datetime | Issue timestamp. |
| `accepted_at` | Read-only datetime | Acceptance timestamp. |
| `accepted_by_id` | Read-only many-to-one to `res.users` | User who accepted or recorded acceptance of the offer. Portal acceptance records the portal user; internal confirmation records the HR manager. |
| `acceptance_source` | Read-only selection | Distinguishes applicant portal acceptance from internal HR confirmation. |
| `declined_at` | Read-only datetime | Decline timestamp. |
| `applicant_response_note` | Text | Applicant or HR response note captured through portal or backend action. |

Issuing an offer requires approved ADM-4A and CM-053 controls for marine crew applicants and prevents a second active offer from being issued at the same time. Offer issue, internal acceptance confirmation, withdrawal, and expiry require the HR Recruitment Manager group server-side. Portal acceptance and decline require ownership checks in the applicant portal controller and record the applicant response against the same offer. Accepting an offer moves the applicant to the offer-accepted stage and unlocks ADM-5. Declined or expired offers close the application through the controlled rejection stage while preserving the offer history.

## `sedar.document.request` recruitment extension

The existing controlled document request is extended so recruitment can use the document catalogue without duplicating forms or attachment storage.

| Field | Type | How it is used |
| --- | --- | --- |
| `applicant_id` | Indexed many-to-one to `hr.applicant` | Application that owns the request; application deletion cascades to its requests. |
| `interview_id` | Indexed many-to-one to `sedar.applicant.interview` | Optional interview that generated the request; deletion clears the link. |
| `sedar_request_purpose` | Selection | Interview appraisal, employment requirements, background check, or orientation. |
| `applicant_visible` | Boolean | Explicitly allows the verified portal owner to view and submit the request. |
| `applicant_submission_note` | Text | Applicant's note accompanying a portal submission. |

Portal submission is restricted to the verified owner, applicant-visible requests, active applications, and editable request states. Typed document values remain governed by Document Control validation; uploaded attachments are stored in the existing binary value field. ADM-5 submission advances the applicant to requirements review. ADM-4A Background Inquiry and CM-053 Company Interview Orientation requests are created as internal-only recruitment controls for marine crew applicants; their detailed content remains hidden from the applicant portal and must be approved before HR can request ADM-5 in the demo workflow.
Internal recruitment document visibility is also restricted by record rules in `sedar_recruitment_operations`: ordinary internal users can read non-recruitment document requests plus recruitment requests assigned to them, assigned to their applicant, or linked to their interview panel. HR Recruitment Managers can read all recruitment document requests and values for supervision. This closes the earlier gap where every internal user inherited broad Document Control access to confidential ADM-4A and orientation content.

## Recruitment operations security hardening

`sedar_recruitment_operations` adds record rules for `sedar.applicant.interview`, `sedar.applicant.offer`, `sedar.document.request`, and `sedar.document.value`.

- Interview access for ordinary recruitment users is limited to coordinator, interviewer, or applicant recruiter assignments. HR Recruitment Managers can supervise all interviews.
- Offer access for ordinary recruitment users is limited to offers for their assigned applicants. HR Recruitment Managers can supervise and act on all offers.
- Recruitment document request and value access is limited to non-recruitment documents, assigned HR users, applicant recruiters, or interview panel users. HR Recruitment Managers can supervise all recruitment documents.
- Server-side actions enforce HR Recruitment Manager authority for background/orientation approval, offer creation/issue/internal acceptance/withdrawal/expiry, and employee conversion/onboarding control.
- Applicant portal routes continue to use ownership checks and `sudo()` only after verifying the signed-in portal user's partner owns the application, interview, document request, or offer.

## Slice 14 ERP demonstration models

These records are explicitly demonstration-only. Standard Odoo Attendance (`hr.attendance`), Time Off (`hr.leave`), Accounting (`account.move`, `account.journal`, and `account.account`), CRM (`crm.lead`), activities, employees, partners, tugboats, crew profiles, and Service Orders remain the source records. The custom models below do not replace Odoo's accounting ledger or payroll engine.

### `sedar.hr.performance.review`

Fields: `name` (Char), `employee_id` (Many2one to `hr.employee`), `reviewer_id` (Many2one to `res.users`), `period_start` and `period_end` (Date), `review_date` (Date), `state` (Selection), `rating` (Selection), `strengths`, `development_goals`, and `manager_summary` (Text), and read-only `demonstration_only` (Boolean). It provides review history because `hr_appraisal` is uninstallable in the shared Odoo edition. It is an HR demonstration record, not a statutory appraisal policy.

### `sedar.hr.payroll.input`

Fields: `name` (Char), `employee_id` (Many2one to `hr.employee`), `period_start` and `period_end` (Date), `attendance_hours`, `approved_leave_hours`, and `eligible_crew_days` (Float), `source_note` (Text), and read-only `demonstration_only` (Boolean). It summarizes source facts for a future payroll integration and deliberately does not calculate Philippine payroll, taxes, or statutory deductions.

### `sedar.finance.budget`

Fields: `name` (Char), `department_id` (Many2one to `hr.department`), `tugboat_id` (Many2one to `sedar.tugboat`), `date_from` and `date_to` (Date), `currency_id` (Many2one to `res.currency`), `planned_amount`, `actual_amount`, and computed `variance` (Monetary), `note` (Text), and read-only `demonstration_only` (Boolean). This is a presentation extension because no installable budget model is available in the shared Odoo edition; it is not a custom ledger.

### `sedar.fixed.asset`

Fields: `name` (Char), `tugboat_id` (Many2one to `sedar.tugboat`), `equipment_id` (Many2one to `maintenance.equipment`), `acquisition_date` (Date), `currency_id` (Many2one to `res.currency`), `original_value` and `residual_value` (Monetary), `useful_life_months` (Integer), computed `monthly_depreciation` and `accumulated_depreciation` (Monetary), and read-only `demonstration_only` (Boolean). It presents straight-line depreciation only because no installable fixed-asset model is available; production accounting must use an approved Odoo asset solution.

### `crm.lead` extensions

`sedar_assisted_vessel_id` (Many2one to `sedar.client.vessel`) records the vessel/service interest, `sedar_service_order_id` (Many2one to `sedar.marine.service.order`) links a resulting marine request, `sedar_service_interest` (Char) labels the requested service, and read-only `sedar_demo_only` (Boolean) marks the seeded example. CRM stages remain sales follow-up states; the linked Service Order remains the operational state machine.

## Slice 15 Corporate Governance and Executive Dashboard

### `sedar.document` extensions

`document_category` (Selection) classifies corporate, vessel, commercial, HSSE, or HR evidence; `owner_id` (Many2one to `res.users`) identifies accountability; `valid_from`, `valid_until`, and `renewal_date` (Date) govern validity; `approval_state` (Selection) records pending, approved, or rejected approval; `confidential` (Boolean) marks restricted evidence; `partner_id` and `tugboat_id` (Many2one) identify related business objects; and computed `governance_status` (Selection) exposes current, renewal due, expired, or no-expiry state. Existing source-file storage and document state remain authoritative for controlled evidence.

### `sedar.corporate.record`

One structured register entry represents a contract, vessel certificate, insurance policy, board resolution, ISO document, legal case, internal audit, or corporate permit. Fields are `name`, `reference`, `record_type`, `description`, and `next_action` (Char/Text); `document_id` (required Many2one to `sedar.document`); `owner_id` (required Many2one to `res.users`); optional `partner_id` and `tugboat_id`; `state` and `approval_state` (Selection); `valid_from`, `valid_until`, and `renewal_date` (Date); `confidential` (Boolean); and computed `compliance_status` and `days_to_expiry`. The register preserves source-document linkage and is restricted to the explicit Executive Management group.

### `sedar.executive.dashboard`

The dashboard is a read-only computed presentation record. It stores only `name`, `company_id`, and `last_refreshed`; all KPI fields are non-stored computed values. Finance indicators query posted `account.move` records and show revenue, invoiced, unpaid, collected, and known posted supplier costs. Operational indicators query `sedar.marine.service.order`, `sedar.marine.operation`, and `sedar.tug.assignment`, including actual/planned tug-hour utilization. Service Order, operation, assignment, shortage, inventory, fuel, and procurement facts are restricted to the dashboard company even though the executive aggregation uses elevated reads. Fleet and people indicators query `sedar.tugboat`, `sedar.crew.profile`, `sedar.crew.certificate`, `sedar.job.vacancy`, and `hr.applicant`; these remain company-neutral where their owning model has no approved company boundary. Maintenance, HSSE, and governance indicators query their owning models directly. Each dashboard action opens a source-model list view; company-owned source drill-downs include the dashboard company and still pass through Odoo access rules. Profitability is intentionally not calculated because attributable fuel, labor, and parts cost rules are not approved.

## Marketing customer workspace

ADR-0005 defines Marketing as a customer-centred workspace over authoritative customer, Service Order, Accounting, and Document Control records. The workspace calls the existing `sedar.marine.service.order` a Service Request in Marketing-facing copy. Marketing quotations and contracts do not create invoices or replace Client Tariffs. Marketing document records store metadata only, and official source-department records are read-only.

### `res.partner` Marketing extensions

Customer-account fields are `sedar_is_customer_account` (Boolean), unique `sedar_customer_code` (Char), `sedar_customer_type`, `sedar_account_status`, and `sedar_relationship_status` (Selection), `sedar_assigned_marketing_user_id` and `sedar_primary_contact_id` (Many2one), `sedar_lead_source` (Char), `sedar_customer_since` and `sedar_next_follow_up_date` (Date), and `sedar_last_interaction_at` (Datetime). The primary contact must belong to the same commercial partner.

Contact fields are `sedar_contact_type_ids` (Many2many to `sedar.marketing.contact.type`), `sedar_contact_status` and `sedar_preferred_contact_method` (Selection), `sedar_availability_day_ids` (Many2many to `sedar.marketing.availability.day`), `sedar_preferred_contact_start` and `sedar_preferred_contact_end` (Float time), `sedar_can_approve_quotations`, `sedar_can_sign_contracts`, and `sedar_can_coordinate_operations` (Boolean), `sedar_contact_internal_notes` (Text), `sedar_last_contacted_at` (Datetime), and computed `sedar_is_primary_contact` (Boolean). The availability end must be later than the start.

Relationship fields `sedar_service_order_ids`, `sedar_marketing_quotation_ids`, `sedar_marketing_contract_ids`, `sedar_marketing_appointment_ids`, `sedar_marketing_document_ids`, `sedar_marketing_document_request_ids`, `sedar_marketing_activity_ids`, `sedar_marketing_note_ids`, and `sedar_marketing_transaction_ids` expose the customer-profile tabs. Computed counters expose total Service Requests, active quotations, active contracts, and completed services.

### `sedar.marketing.contact.type` and `sedar.marketing.availability.day`

Contact types have unique `code`, `name`, `sequence`, and `active`. Availability days have unique `code`, `name`, and `sequence`. Marketing Managers maintain these configuration records; Marketing Officers read them.

### `sedar.marine.service.order` Marketing extensions

`marketing_status` stores the Marketing lifecycle from draft through review, Operations consultation, quotation, customer approval, scheduling, completion, or cancellation without replacing the operational `state`. `marketing_representative_id` and `requested_operations_reviewer_id` identify accountable users; `marketing_tag_ids` links `sedar.marketing.tag`; `marketing_internal_notes` and `marketing_follow_up_date` hold restricted working context. `marketing_quotation_ids` and `marketing_contract_ids` expose related commercial records. The inherited `priority` selection adds High. Operational completion and cancellation synchronize the Marketing status, while operational readiness and execution remain owned by the existing Service Order workflow.

### `sedar.marketing.quotation` and `sedar.marketing.quotation.line`

A quotation has unique `name`, `revision_number`, `original_quotation_id`, `supersedes_quotation_id`, and `superseded_by_quotation_id`; required `service_order_id`, `customer_id`, and `contact_id`; `subject`, `purchase_order_reference`, terms, response, revision, and internal-note fields; `line_ids`; computed untaxed, tax, and total amounts; `currency_id`; validity and issue dates; `prepared_by_id`; and tracked `status`. The status lifecycle is Draft, For Internal Approval, Ready to Send, Sent, Viewed, Customer Approved, Rejected, Expired, or Superseded. Customer/contact relationships are validated, revisions preserve their family, and quotation approval may advance the Marketing-facing Service Request without bypassing its operational lifecycle.

Quotation lines store `sequence`, required parent and `description`, positive `quantity`, non-negative `unit_price` and `tax_rate`, related currency, and computed subtotal and tax. They are commercial offer lines only and never post accounting entries.

### `sedar.marketing.contract` and `sedar.marketing.contract.signature`

A contract has unique `name`, `title`, required customer/contact/quotation/Service Request links, related service and vessel context, description and terms, required effective and expiration dates, monetary value and currency, prepared/managed users, tracked contract and computed signature statuses, signature records, selected authorized contact, signature timestamps, termination-request fields, and supersession links. The contract lifecycle is Draft, For Internal Review, Ready for Signature, Awaiting Signatures, Active, Terminated, Expired, or Superseded. Activation requires verified SEDAR and customer signatures; termination requires a reviewed request. The record does not replace the Client Tariff or control invoicing.

A signature record stores required contract and party, signatory identity and organization, role, signing time, recording user, supporting-document filename metadata, verification status, and internal notes. Signature image or file bytes are deliberately excluded.

### `calendar.event` Marketing extensions and `sedar.marketing.appointment.status`

`calendar.event` is extended with a Marketing flag; customer and contact; appointment type and status; meeting method, phone/video metadata; optional Service Request, quotation, and contract links; agenda, customer-visible and internal notes; follow-up controls; outcome, response, next action, and no-show party; and status history. Customer and contact must share a commercial partner. Standard Calendar owns the event start, stop, attendees, assigned user, location, and calendar display.

`sedar.marketing.appointment.status` stores the appointment, previous and next status, occurrence time, changing user, reason, notes, and previous start/stop. It is read-only to Marketing users and records confirmation, rescheduling, completion, cancellation, and no-show transitions.

### `sedar.marketing.document`, `sedar.marketing.document.version`, and `sedar.marketing.document.request`

A Marketing document stores a unique reference, customer, title and description, document type, owning department, Marketing-only/shared visibility, Marketing-upload/official source, active/expired/archived status, expiry date, optional links to a Service Request, quotation, contract, invoice, appointment, or official `sedar.document`, version metadata, current version, creator/update/archive audit fields, and computed editability. It stores no file bytes. Marketing may edit, version, archive, restore, or delete only Marketing-owned upload records; official and other-department records are read-only.

Version metadata stores the parent, immutable version number, filename, MIME type, byte size, upload time/user, and notes. Versions are append-only and capped at 25 MB of reported size. A document request stores its reference, customer, title/type/description, requester/time, due date, department, pending/fulfilled/cancelled status, fulfillment document/audit fields, and cancellation reason.

### `sedar.marketing.activity`

The append-only activity log stores customer, occurrence time, module, action, description, actor identity/type/department, visibility, related model/record/reference, sanitized before/after summary, idempotent source-event key, and system-generated flag. Marketing users have read-only access. Passwords, tokens, bank/tax/payment credentials, file content, signature images, and other restricted fields are replaced by `Restricted field updated`; entries cannot be changed or deleted.

### `sedar.marketing.transaction`

The read-only transaction projection stores customer, occurrence time, transaction type, reference, description, amount/currency, normalized status, source department, visibility, source model/record, and optional vessel/service/PO context. Service Requests, completed services, quotations, contracts, invoices, credit notes, and invoice-derived payment facts synchronize from their owning records. Marketing users cannot create, edit, or delete projections.

### `sedar.marketing.internal.note`, `sedar.marketing.tag`, and `sedar.marketing.dashboard`

An internal note stores customer, immutable author, and note text and creates a restricted activity entry. A tag stores a unique name and display color. The dashboard stores only its name and company; all counts, upcoming appointment, recent activities, and recent notes are computed from the authoritative records above.

### `account.move` Marketing behavior

The method-only extension synchronizes linked SEDAR customer invoices, credit notes, and invoice-derived payment state into the read-only Marketing transaction projection. It does not change posting, receivables, payment, reconciliation, or ledger behavior owned by Odoo Accounting and ADR-0001.

### `res.company` Marketing behavior

The method-only `sedar_ensure_marketing_workspace()` reconciliation assigns the Marketing Manager role to the shared administrator, marks existing Service Order clients as customer accounts, assigns stable customer codes where missing, ensures the singleton dashboard exists, and refreshes the read-only transaction projection. The post-install hook, upgrade data function, and shared demo-suite reconciliation call the same idempotent method so a fresh Docker setup and a module upgrade produce the same workspace.

The Marketing post-install and shared demo-suite hooks also run the repeatable `ensure_marketing_demo()` bootstrap after the Service Order fixtures exist. It owns only fictional demonstration records identified by stable `sedar_marketing` XML IDs: an approved and a pending quotation, an executed contract with verified signature metadata, an upcoming customer appointment, a versioned Marketing document metadata record, a pending document request, and an internal note. Reconciliation updates those records without duplicating them and does not store file bytes, create invoices, or alter the authoritative operational and accounting workflows.

## Simulated AIS Fleet Monitoring

### `sedar.ais.position`

One current demonstration position is stored per tugboat. AIS Fleet Monitoring Users may read the
feed, while AIS Simulation Managers may advance or maintain it. Records may not be deleted through
normal access. The dashboard service combines these simulated positions with authoritative tugboat,
crew assignment, Marine Operation, maintenance-request, and dry-dock records.

| Field | Type | How it is used |
| --- | --- | --- |
| `tugboat_id` | Required unique many-to-one to `sedar.tugboat` | Tugboat represented by the current report; deleting the tugboat cascades to its simulated position. |
| `latitude`, `longitude` | Required float | Fictional geographic position, constrained to valid coordinate ranges. |
| `previous_latitude`, `previous_longitude` | Float | Previous fictional report used to animate movement toward the current waypoint. |
| `speed_knots` | Float | Non-negative fictional speed over ground in knots. |
| `course_degrees` | Float | Fictional course constrained to 0–359 degrees. |
| `navigation_status` | Required selection | Underway, assisting, standby, berthed, dry dock, maintenance hold, or signal offline. |
| `location_label`, `destination` | Character | Human-readable fictional operating area and destination. |
| `eta` | Datetime | Optional fictional estimated arrival. |
| `last_reported_at` | Required datetime | Time at which the simulation produced the current report. |
| `signal_quality` | Required selection | Strong, fair, or weak simulated signal presentation. |
| `route_index` | Integer | Internal pointer to the next fictional waypoint. |
| `simulated` | Read-only boolean | Permanently identifies the record as non-live demonstration data. |

### `sedar.tugboat` AIS extension

`ais_position_ids` is a one-to-many relationship to `sedar.ais.position`. The uniqueness constraint
on the position model means it exposes at most one current simulated report per tugboat.

### `res.company` AIS demo extension

`sedar_ensure_ais_demo()` reconciles the fictional fleet-monitoring user and one simulated position
per seeded tugboat. The method is used only for repeatable demonstration bootstrap and upgrade.

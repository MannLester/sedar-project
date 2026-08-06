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
requirements. For the local demonstration only, reconciliation also grants Odoo's built-in
Administrator the highest SEDAR manager role in every installed workspace so every visible
sidebar destination opens without switching accounts. Dedicated role accounts retain their
normal restrictions, and the Administrator exception does not apply outside that seeded user.
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
| `res.company` | Method-only extension | Configures demo currency and reconciles repeatable fictional recruitment and crew-onboarding demonstration records | `sedar_service_order_demo/models/res_company.py`; `sedar_recruitment_demo/models/res_company.py`; `sedar_recruitment_crewing/models/res_company.py` |
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
| `sedar.tugboat` | Extended | Exposes technical equipment, maintenance blockers, dry-dock plans, readiness reason, tugboat stock location, and HSSE exceptions | `sedar_marine_maintenance/models/tugboat.py`; `sedar_marine_inventory/models/tugboat.py`; `sedar_hsse/models/hsse.py` |
| `sedar.ais.position` | New | Stores the current fictional AIS/GPS report consumed by the offline fleet-monitoring demonstration | `sedar_ais_demo/models/ais_position.py` |
| `maintenance.equipment` | Extended | Links standard Odoo equipment to SEDAR tugboats and marine equipment hierarchy/criticality | `sedar_marine_maintenance/models/maintenance_equipment.py` |
| `maintenance.request` | Extended | Adds SEDAR work-order type, tug availability impact, release evidence, dry-dock linkage, and spare-part status/lines | `sedar_marine_maintenance/models/maintenance_request.py`; `sedar_marine_inventory/models/maintenance_parts.py` |
| `sedar.drydock.plan` | New | Represents dry-dock planning, milestones, availability impact, and controlled release | `sedar_marine_maintenance/models/drydock.py` |
| `sedar.drydock.milestone` | New | Tracks planned and actual dry-dock milestones | `sedar_marine_maintenance/models/drydock.py` |
| `sedar.inventory.template` | New | Defines stock-backed inventory requirements generated for a Service Order service type | `sedar_marine_inventory/models/inventory_models.py` |
| `sedar.inventory.template.line` | New | Defines product quantities required by an inventory template | `sedar_marine_inventory/models/inventory_models.py` |
| `sedar.inventory.requirement` | New | Stores generated or manual stock requirements that drive the inventory component of readiness | `sedar_marine_inventory/models/service_order.py` |
| `product.product` | Extended | Provides the SEDAR Inventory Check item identity, warehouse availability, reorder status, and tug compatibility | `sedar_marine_inventory/models/inventory_item.py` |
| `sedar.inventory.issue` | New | Preserves the immutable audit record and Odoo stock movement for one-step issuance to a tugboat | `sedar_marine_inventory/models/inventory_item.py` |
| `sedar.maintenance.part.line` | New | Tracks requested, reserved, issued, and consumed spare parts for maintenance work orders | `sedar_marine_inventory/models/maintenance_parts.py` |
| `sedar.operation.fuel.log` | New | Tracks operation fuel/lubricant issue, consumption, and remaining balance by tugboat | `sedar_marine_inventory/models/operation_fuel.py` |
| `sedar.marine.operation` | Extended | Exposes operation fuel/lubricant logs and consumption summary | `sedar_marine_inventory/models/operation_fuel.py` |
| `sedar.purchase.request` | New | Captures department purchase requests, approval, and the handoff to standard Odoo RFQs/Purchase Orders | `sedar_purchase_request/models/purchase_request.py` |
| `sedar.purchase.request.line` | New | Captures requested products, quantities, estimated costs, and maintenance/inventory source traceability | `sedar_purchase_request/models/purchase_request.py` |
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

No new field was added to the PM-owned model, but its lifecycle contract changed materially:

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
| `sedar_service_order_id` | Indexed many-to-one to `sedar.marine.service.order` | Links a customer invoice to its originating Service Order. The link is copied neither to duplicates nor removable while referenced by the invoice. |

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
| `action_type` | Selection extension | Adds `temporary_reliever` alongside existing replacement, reschedule, certificate, medical, training, and manpower actions. |
| `relief_crew_profile_id` | Many-to-one to `sedar.crew.profile` | Candidate relief crew for a temporary reliever action. |
| `relief_assignment_id` | Read-only many-to-one to `sedar.crew.assignment` | Concrete Service Order crew assignment created after the relief candidate passes eligibility checks. |
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
| `sedar_running_interval_hours` | Float | Representative planned-maintenance interval in running hours. Real intervals require SEDAR confirmation. |
| `sedar_last_service_date` | Date | Last verified service date for PMS visibility. |
| `sedar_last_service_hours` | Float | Last service running-hour reading. |

### `maintenance.request` marine extension

| Field | Type | How it is used |
| --- | --- | --- |
| `sedar_tugboat_id` | Many-to-one to `sedar.tugboat` | Affected tugboat. Defaults from linked marine equipment when available. |
| `sedar_work_order_type` | Selection | Planned maintenance, defect/corrective, or dry-dock work. |
| `sedar_priority` | Selection | Low, medium, high, or critical marine priority. |
| `sedar_defect_source` | Character | Source of a corrective defect report. Required for defect work orders. |
| `sedar_availability_impact` | Selection | No impact, monitor only, or blocks tug readiness. |
| `sedar_blocks_tug_readiness` | Computed, stored boolean | True when availability impact is blocking and the work order is not closed. |
| `sedar_drydock_plan_id` | Many-to-one to `sedar.drydock.plan` | Optional dry-dock plan that owns or groups the work order. |
| `sedar_spare_part_note` | Text | Legacy placeholder retained for historical Slice 10 records; Slice 11 uses structured spare-part lines. |
| `sedar_part_line_ids` | One-to-many to `sedar.maintenance.part.line` | Spare parts requested, reserved, issued, and consumed for the work order. |
| `sedar_parts_status` | Computed, stored selection | Summarizes whether the work order has no parts, shortage, reserved, issued, or consumed parts. |
| `sedar_running_hours_at_service` | Float | Running-hour reading at service verification. |
| `sedar_closure_note` | Text | Required verification note before releasing a blocking work order. |
| `sedar_released_by_id` | Read-only many-to-one to `res.users` | Marine Maintenance Manager who released the tug from the work-order hold. |
| `sedar_released_at` | Read-only datetime | Release timestamp. |

Key behavior:

- Blocking work orders require an affected tugboat.
- Defect work orders require a defect source.
- `action_sedar_mark_blocking()` is restricted to Marine Maintenance Managers and places the affected tugboat on maintenance hold.
- `action_sedar_release_tug()` is restricted to Marine Maintenance Managers, requires a closure note, closes the work order if needed, records release audit fields, and restores the tug only when no other technical blocker remains.

### `sedar.drydock.plan`

One record represents a planned dry-dock event for one tugboat. It provides planning visibility without inventing SEDAR regulatory intervals.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required character | Dry-dock plan title. |
| `tugboat_id` | Required many-to-one to `sedar.tugboat` | Tugboat affected by the dry dock. |
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
| `plan_id` | Required many-to-one to `sedar.drydock.plan` | Parent dry-dock plan. |
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
| `sedar_compatibility_scope` | Required selection | Marks an Item Type as fleet-wide or restricted to selected tugboats. |
| `sedar_compatible_tugboat_ids` | Many-to-many to `sedar.tugboat` | Explicit list required for restricted compatibility. |
| `sedar_reorder_point` | Float | Manually maintained low-stock threshold; cannot be negative. |
| `sedar_stock_location_id` | Computed many-to-one to `stock.location` | Current company's primary warehouse stock location. |
| `sedar_on_hand_qty` | Computed float | Physical quantity at the exact warehouse stock location. |
| `sedar_reserved_qty` | Computed float | Quantity reserved at that exact location. |
| `sedar_available_to_issue` | Computed float | On Hand minus Reserved at that exact warehouse location. |
| `sedar_stock_status` | Computed selection | In Stock, Low Stock, or Out of Stock from Available to Issue and Reorder Point. |
| `sedar_compatibility_display` | Computed character | Fleet-wide or a readable list of compatible tugboats. |
| `sedar_code_locked` | Computed boolean | Makes the SEDAR Item Code immutable after the first non-cancelled stock movement. |

Key behavior:

- The SEDAR Item Code (`default_code` in the Odoo product foundation) is required and unique among SEDAR Inventory Items.
- Restricted Item Types require at least one explicitly compatible tugboat.
- Inventory Check excludes quantities stored in child and tug locations from Available to Issue.
- Procurement and Inventory Officers may create and maintain Item Types but cannot directly edit stock balances or change an Item Code after stock movement begins.

### `sedar.inventory.issue`

One record is an immutable issue of an Item Type from warehouse stock to a named tugboat. The initial workflow treats issuance as immediate consumption and does not maintain an onboard balance.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required read-only character | Sequence-generated reference using `SII/<year>/#####`. |
| `product_id` | Required read-only many-to-one to `product.product` | Issued Item Type. |
| `manufacturer_part_number` | Read-only related character | Manufacturer reference visible in the audit record. |
| `tugboat_id` | Required read-only many-to-one to `sedar.tugboat` | Tugboat receiving the issued item. |
| `source_location_id` | Required read-only many-to-one to `stock.location` | Exact warehouse location reduced by the issue. |
| `quantity` | Required read-only float | Quantity issued; must be positive and no greater than Available to Issue. |
| `product_uom_id` | Read-only related many-to-one to `uom.uom` | Product unit of measure. |
| `purpose` | Required read-only text | Operational reason for the issue. |
| `issued_by_id` | Required read-only many-to-one to `res.users` | Procurement and Inventory Officer who confirmed the issue. |
| `issued_at` | Required read-only datetime | Confirmation time. |
| `stock_move_id` | Required read-only many-to-one to `stock.move` | Completed Odoo movement from warehouse to the controlled consumption location. |

Key behavior:

- Issue to Tug hard-blocks incompatible tugboats and insufficient Available to Issue.
- Completion creates a standard done Odoo stock movement and then the immutable SEDAR audit record.
- Completed issues cannot be edited or deleted.
- Return to Warehouse and issuance-correction rules are deliberately deferred and marked inline for the next inventory iteration.

### `sedar.tugboat` inventory extension

| Field | Type | How it is used |
| --- | --- | --- |
| `stock_location_id` | Many-to-one to `stock.location` | Internal stock location representing onboard fuel, lubricant, and vessel stores assigned to the tugboat. |

### `sedar.inventory.template`

One record defines the stock products normally required for one Service Order service type.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Required character | Template label. |
| `service_type_id` | Required many-to-one to `sedar.marine.service.type` | Service type that triggers this requirement template. |
| `tug_class_id` | Many-to-one to `sedar.tug.class` | Optional tug-class-specific requirement rule. |
| `source_location_id` | Required many-to-one to `stock.location` | Internal stock location checked for available quantity. |
| `line_ids` | One-to-many to `sedar.inventory.template.line` | Products and quantities generated for matching Service Orders. |
| `active` | Boolean | Allows old demo templates to be retired without deleting history. |

### `sedar.inventory.template.line`

| Field | Type | How it is used |
| --- | --- | --- |
| `template_id` | Required many-to-one to `sedar.inventory.template` | Parent template. |
| `sequence` | Integer | Display order. |
| `product_id` | Required many-to-one to `product.product` | Stock product required by the Service Order. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `required_qty` | Required float | Base required quantity; must be greater than zero. |
| `per_tug` | Boolean | Multiplies the required quantity by `number_of_tugs` when generated. |

### `sedar.inventory.requirement`

One record is a stock-backed Service Order inventory requirement. It replaces the manual Inventory Readiness Confirmation whenever requirement lines exist.

| Field | Type | How it is used |
| --- | --- | --- |
| `order_id` | Required many-to-one to `sedar.marine.service.order` | Parent Service Order. |
| `product_id` | Required many-to-one to `product.product` | Required stock product. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `source_location_id` | Required many-to-one to `stock.location` | Internal location checked for available quantity. |
| `required_qty` | Required float | Required quantity; must be greater than zero. |
| `available_qty` | Computed, stored float | Available quantity from standard Odoo stock quants at the source location. |
| `shortage_qty` | Computed, stored float | Required quantity not currently available. |
| `readiness_state` | Computed, stored selection | `ready` or `shortage`; feeds the Dispatch Readiness Gate. |
| `auto_generated` | Boolean | Marks lines generated from a Service Order inventory template. |
| `note` | Text | Optional operational inventory note. |

Key behavior:

- `action_generate_inventory_requirements()` regenerates auto-generated requirement lines from the matching template for planned, blocked, or ready Service Orders.
- `_sync_inventory_readiness()` writes the legacy `inventory_ready` flag from requirement-line availability only when requirement lines exist.
- `action_confirm_inventory_ready()` is blocked for orders with requirement lines because readiness is stock-derived.
- Service Order readiness shows `waiting_inventory` with a shortage summary when any requirement line is short.

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
| `product_id` | Required many-to-one to `product.product` | Spare-part product. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `source_location_id` | Required many-to-one to `stock.location` | Internal stock location used for the issue. |
| `requested_qty` | Required float | Required part quantity; must be greater than zero. |
| `available_qty` | Computed, stored float | Current available stock at the source location. |
| `reserved_qty` | Float | Quantity reserved for the work order in the demo control. |
| `issued_qty` | Float | Quantity issued from stock for the work order. |
| `consumed_qty` | Float | Quantity consumed by the work order. |
| `shortage_qty` | Computed, stored float | Quantity still short. |
| `state` | Computed, stored selection | Shortage, reserved, issued, or consumed. |
| `note` | Text | Optional maintenance inventory note. |

Key behavior:

- Reserve, issue, and consume actions are restricted to Marine Inventory Managers.
- Issuing parts decreases standard Odoo stock quantity at the source location.
- Consumed quantity cannot exceed issued quantity, and issued quantity cannot exceed reserved quantity.

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
| `tugboat_id` | Required many-to-one to `sedar.tugboat` | Tugboat consuming fuel or lubricant. |
| `product_id` | Required many-to-one to `product.product` | Fuel or lubricant product. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure. |
| `source_location_id` | Required many-to-one to `stock.location` | Internal source stock location. |
| `tug_location_id` | Required many-to-one to `stock.location` | Tugboat onboard stock location. |
| `opening_qty` | Float | Starting onboard quantity for the operation. |
| `issued_qty` | Float | Quantity issued from source stock to the tugboat. |
| `consumed_qty` | Float | Quantity consumed during the operation. |
| `remaining_qty` | Computed, stored float | Opening plus issued minus consumed quantity. |
| `state` | Selection | Draft, issued, or consumption recorded. |
| `note` | Text | Optional operational fuel note. |

Key behavior:

- Issue and consumption actions are restricted to Procurement and Inventory Officers.
- Issuing decreases source stock and increases tugboat stock.
- Recording consumption decreases tugboat stock and updates operation fuel summary.
- Consumption cannot exceed opening plus issued quantity.

Access rules:

- Inventory Check Users can read Inventory Check records, immutable issue history, inventory templates, Service Order requirements, maintenance part lines, and operation fuel logs.
- Procurement and Inventory Officers may maintain Item Types and use controlled issue actions, but cannot directly edit stock balances or alter completed Inventory Issues.
- Operations Managers can read Service Order inventory requirements and operation fuel logs for dispatch and operational context.
- Marine Maintenance Users can read and maintain work-order spare-part lines for maintenance execution context.

## Procurement Handoff

Slice 12 adds `sedar_purchase_request`, a focused procurement-control addon on top of standard Odoo Purchase. SEDAR owns the request, approval, and source traceability. Standard `purchase.order`, stock receipts, supplier bills, payments, and accounting entries remain owned by Odoo Purchase, Inventory, and Accounting.

### `sedar.purchase.request`

One record is a department request to buy goods needed by maintenance, inventory, operations, or a manual business need.

| Field | Type | How it is used |
| --- | --- | --- |
| `name` | Read-only character | Sequence-generated request number using `SPR/<year>/#####`. |
| `requester_id` | Required many-to-one to `res.users` | User requesting the purchase. |
| `department_id` | Many-to-one to `hr.department` | Optional requesting department. |
| `company_id` | Required many-to-one to `res.company` | Company context for the request and generated RFQ. |
| `currency_id` | Required many-to-one to `res.currency` | Currency for estimated request totals and generated RFQ lines. |
| `vendor_id` | Many-to-one to `res.partner` | Preferred supplier; required before approval and RFQ creation. |
| `source_type` | Required selection | Maintenance, inventory, operations, or manual source classification. |
| `maintenance_request_id` | Many-to-one to `maintenance.request` | Optional work-order source for spare-part replenishment. |
| `service_order_id` | Many-to-one to `sedar.marine.service.order` | Optional Service Order source for operations or inventory replenishment. |
| `required_date` | Required datetime | Need-by date copied to the generated RFQ planned date. |
| `priority` | Required selection | Normal, urgent, or emergency. |
| `justification` | Required text | Business reason for the purchase. |
| `line_ids` | One-to-many to `sedar.purchase.request.line` | Requested products, quantities, estimated costs, and source traceability. |
| `purchase_order_id` | Read-only many-to-one to `purchase.order` | Standard Odoo RFQ/Purchase Order created from the approved request. |
| `purchase_order_state` | Related selection | Mirrors the linked standard RFQ/PO state for visibility. |
| `state` | Required selection | Draft, submitted, approved, RFQ created, rejected, or cancelled. |
| `approved_by_id` | Read-only many-to-one to `res.users` | Manager who approved the request. |
| `approved_at` | Read-only datetime | Approval timestamp. |
| `rejected_by_id` | Read-only many-to-one to `res.users` | Manager who rejected the request. |
| `rejected_at` | Read-only datetime | Rejection timestamp. |
| `rejection_reason` | Text | Required explanation before rejection. |
| `estimated_total` | Computed, stored monetary | Sum of all request-line estimated subtotals. |

Key behavior:

- `action_submit()` requires at least one request line and moves draft or rejected requests to submitted.
- `action_approve()` requires Purchase Request Manager authority, submitted state, a preferred vendor, and records approval audit fields.
- `action_reject()` requires Purchase Request Manager authority and a rejection reason.
- `action_create_rfq()` requires Purchase Request Manager authority, approved state, a preferred vendor, and creates one standard Odoo `purchase.order` with standard `purchase.order.line` records.
- RFQ creation is idempotent from the request side; a second RFQ cannot be created for the same Purchase Request.
- Generated RFQs use the Purchase Request number in `purchase.order.origin` so downstream receipts and supplier bills remain traceable without custom accounting records.

### `sedar.purchase.request.line`

One record is one requested product line under a Purchase Request.

| Field | Type | How it is used |
| --- | --- | --- |
| `request_id` | Required many-to-one to `sedar.purchase.request` | Parent Purchase Request; deleting the request cascades to its lines. |
| `sequence` | Integer | Line display order. |
| `product_id` | Required many-to-one to `product.product` | Product to purchase. |
| `product_uom_id` | Related, stored many-to-one to `uom.uom` | Product unit of measure used on the RFQ line. |
| `quantity` | Required float | Requested quantity; must be greater than zero. |
| `estimated_unit_price` | Monetary | Estimated supplier unit cost; cannot be negative. |
| `currency_id` | Related, stored many-to-one to `res.currency` | Currency inherited from the parent request. |
| `estimated_subtotal` | Computed, stored monetary | Quantity multiplied by estimated unit price. |
| `source_location_id` | Many-to-one to `stock.location` | Internal stock location whose shortage or replenishment need triggered the request. |
| `maintenance_part_line_id` | Many-to-one to `sedar.maintenance.part.line` | Optional maintenance spare-part shortage source. |
| `inventory_requirement_id` | Many-to-one to `sedar.inventory.requirement` | Optional Service Order inventory shortage source. |
| `need_reason` | Text | Optional line-specific explanation. |

Key behavior:

- Selecting a maintenance part line or inventory requirement populates product, quantity, and source location.
- A request line may reference either one maintenance part line or one inventory requirement, not both.
- The line validates positive quantity and non-negative estimated unit price.

Access rules:

- Purchase Request Users can create, read, and update Purchase Requests and lines, but cannot delete them through normal access.
- Marine Inventory Users and Marine Maintenance Users can create, read, and update requests so stock and maintenance shortages can become procurement requests.
- Purchase Request Managers inherit standard Odoo Purchase Manager authority and control approval, rejection, and RFQ creation server-side.
- The addon does not add fields to `purchase.order` and does not create receipts, supplier bills, payments, or ledger entries.

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

No new field is added to either model in this slice, but their workflow contract changed materially under ADR-0003:

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

The dashboard is a read-only computed presentation record. It stores only `name`, `company_id`, and `last_refreshed`; all KPI fields are non-stored computed values. Finance indicators query posted `account.move` records and show revenue, invoiced, unpaid, collected, and known posted supplier costs. Operational indicators query `sedar.marine.service.order`, `sedar.marine.operation`, and `sedar.tug.assignment`, including actual/planned tug-hour utilization. Fleet and people indicators query `sedar.tugboat`, `sedar.crew.profile`, `sedar.crew.certificate`, `sedar.job.vacancy`, `hr.applicant`, and `sedar.crew.shortage`. Maintenance, inventory, procurement, HSSE, and governance indicators query their owning models directly. Each dashboard action opens a source-model list view; executive aggregation uses the explicit Executive Management role while source drill-downs continue through Odoo access rules. Profitability is intentionally not calculated because attributable fuel, labor, and parts cost rules are not approved.

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

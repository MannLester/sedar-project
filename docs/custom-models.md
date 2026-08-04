# Custom Model Reference

This document records the Odoo models and fields introduced or extended by the SEDAR service-completion and finance MVP. It covers the local changes built on top of the existing Marine Operations, Marine Dispatch, and Odoo Accounting models. It does not attempt to document unrelated models owned by the manpower, applicant-intake, or careers modules.

Update this document in the same change whenever a listed custom field is added, renamed, removed, or given a materially different workflow meaning.

## Model summary

| Model | Change type | Purpose | Main source |
| --- | --- | --- | --- |
| `sedar.tug.assignment` | Extended | Records the assigned Tug Master's actual service time and completion declaration for one tug | `sedar_marine_operations/models/marine_crew.py` |
| `sedar.marine.service.order` | Extended | Applies automated tug/crew/inventory readiness, aggregates tug completions, freezes confirmed pricing, and tracks billing/payment | `sedar_marine_operations/models/marine_service_order.py`; `sedar_marine_dispatch/models/marine_service_order.py`; `sedar_marine_finance/models/marine_finance.py` |
| `sedar.marine.operation` | Workflow changed | Provides the automatically created execution record whose time and completion follow Tug Master records | `sedar_marine_dispatch/models/marine_operation.py` |
| `sedar.client.tariff` | Extended | Governs client- and terminal-specific tariff approval and revision history | `sedar_marine_finance/models/marine_finance.py` |
| `sedar.marine.billing.adjustment` | New | Stores explained charges or deductions included in the final invoice | `sedar_marine_finance/models/marine_finance.py` |
| `account.move` | Extended | Links the standard Odoo customer invoice back to its Marine Service Order | `sedar_marine_finance/models/account_move.py` |
| `res.company` | Method-only extension | Configures the demo company and seeded commercial records to use PHP | `sedar_service_order_demo/models/res_company.py` |
| `res.users` | Method-only extension | Assigns the custom Service Order dashboard as the default home action for internal users | `sedar_theme/models/res_users.py` |

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
| `inventory_ready` | Tracked boolean | Temporary manual confirmation that required inventory is ready. Its inline help states that the dedicated Inventory module will revamp and replace this band-aid control. |
| `inventory_ready_by_id` | Read-only many-to-one to `res.users` | Audit identity of the authorized Operations user who confirmed inventory readiness. |
| `inventory_ready_at` | Read-only datetime | Audit time of the current inventory confirmation. |

The `readiness_status` selection now includes `waiting_inventory`. Relevant changes to service, scope, tug requirements, terminal, schedule, cargo, permits, or safety requirements clear all three inventory confirmation fields. Automated dispatch creates one awaiting-start Marine Operation only when tugboat, crew, and inventory readiness all pass.

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

## `res.users` theme extension

No field is added. `sedar_set_default_home_action()` assigns the Marine Operations Service Order dashboard to the standard `action_id` field of every internal user. The theme bootstrap calls it so a fresh shared Docker installation opens on the team's custom dashboard instead of the stock Odoo home screen. If the dashboard action is unavailable, the method exits without changing users.

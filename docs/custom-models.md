# Custom Model Reference

This document records the Odoo models and fields introduced or extended by the SEDAR service-completion, finance, applicant portal, and recruitment-operations MVP. It covers the local changes built on top of the existing Marine Operations, Marine Dispatch, Odoo Accounting, Odoo Recruitment, and SEDAR Document Control models. It does not attempt to document unrelated models owned by the manpower, applicant-intake, or careers modules.

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
| `res.company` | Method-only extension | Configures demo currency and reconciles repeatable fictional recruitment demonstration records | `sedar_service_order_demo/models/res_company.py`; `sedar_recruitment_demo/models/res_company.py` |
| `res.users` | Method-only extension | Assigns the custom Service Order dashboard as the default home action for internal users | `sedar_theme/models/res_users.py` |
| `hr.recruitment.stage` | Extended | Maps internal recruitment stages to applicant-visible statuses and instructions | `sedar_applicant_portal/models/portal.py` |
| `hr.applicant` | Extended | Owns portal access, public tracking, HR processing, interviews, requirements, and employee conversion | `sedar_applicant_portal/models/portal.py`; `sedar_recruitment_operations/models/applicant.py` |
| `sedar.applicant.portal.event` | New | Stores applicant-visible timeline events | `sedar_applicant_portal/models/portal.py` |
| `sedar.applicant.stage.history` | New | Provides an auditable history of HR stage changes | `sedar_recruitment_operations/models/applicant.py` |
| `sedar.applicant.interview` | New | Coordinates interview scheduling, applicant responses, calendar events, and ADM-4 appraisal | `sedar_recruitment_operations/models/interview.py` |
| `sedar.document.request` | Extended | Links controlled document requests to applicants and interviews and governs portal visibility | `sedar_recruitment_operations/models/interview.py` |

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

`sedar_recruitment_demo` also adds the method-only `sedar_ensure_recruitment_demo()` extension.
It creates and reconciles fictional HR users, portal ownership, recruitment applicants,
ADM-3 profile/supporting records, interviews, ADM-4 appraisal requests, ADM-5 requirement
requests, and one converted employee. The method is invoked by XML data during module install
and upgrade so the Slice 1 recruitment baseline is repeatable. It uses stable external IDs under
the `sedar_recruitment_demo` module and avoids deleting or replacing unrelated user-created
records.

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
| `sedar_is_overdue` | Computed, searchable boolean | Identifies applications whose next-action date is before today. |

Workflow actions move applicants through controlled SEDAR stages, synchronize the public status, and create stage history. Interview completion requires a submitted ADM-4 appraisal. Employment-requirement verification requires an ADM-5 request to be submitted and approved. Employee conversion uses Odoo Recruitment's native employee creation and is blocked until the approved ADM-5 request exists.

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

## `sedar.document.request` recruitment extension

The existing controlled document request is extended so recruitment can use the document catalogue without duplicating forms or attachment storage.

| Field | Type | How it is used |
| --- | --- | --- |
| `applicant_id` | Indexed many-to-one to `hr.applicant` | Application that owns the request; application deletion cascades to its requests. |
| `interview_id` | Indexed many-to-one to `sedar.applicant.interview` | Optional interview that generated the request; deletion clears the link. |
| `sedar_request_purpose` | Selection | Interview appraisal, employment requirements, background check, or orientation. |
| `applicant_visible` | Boolean | Explicitly allows the verified portal owner to view and submit the request. |
| `applicant_submission_note` | Text | Applicant's note accompanying a portal submission. |

Portal submission is restricted to the verified owner, applicant-visible requests, active applications, and editable request states. Typed document values remain governed by Document Control validation; uploaded attachments are stored in the existing binary value field. ADM-5 submission advances the applicant to requirements review.

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
| `res.company` | Method-only extension | Configures demo currency and reconciles repeatable fictional recruitment and crew-onboarding demonstration records | `sedar_service_order_demo/models/res_company.py`; `sedar_recruitment_demo/models/res_company.py`; `sedar_recruitment_crewing/models/res_company.py` |
| `res.users` | Method-only extension | Assigns the custom Service Order dashboard as the default home action for internal users | `sedar_theme/models/res_users.py` |
| `hr.recruitment.stage` | Extended | Maps internal recruitment stages to applicant-visible statuses and instructions | `sedar_applicant_portal/models/portal.py` |
| `hr.applicant` | Extended | Owns portal access, public tracking, HR processing, interviews, requirements, employee conversion, and the marine crewing handoff | `sedar_applicant_portal/models/portal.py`; `sedar_recruitment_operations/models/applicant.py`; `sedar_recruitment_crewing/models/applicant.py` |
| `hr.employee` | Extended | Preserves traceability from successful applicant conversion into the HR employee master, controls generic HR onboarding, and exposes linked marine crew onboarding cases | `sedar_recruitment_operations/models/employee.py`; `sedar_recruitment_crewing/models/employee.py` |
| `sedar.crew.onboarding` | New | Controls the handoff from a marine employee to a deployment-eligible Crew Profile | `sedar_recruitment_crewing/models/crew_onboarding.py` |
| `sedar.crew.certificate` | Extended | Links crew credentials and medicals to controlled document evidence, renewal status, and readiness eligibility | `sedar_crew_compliance/models/crew_certificate.py`; `sedar_crew_compliance/models/crew_assignment.py`; `sedar_crew_compliance/models/crew_onboarding.py` |
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

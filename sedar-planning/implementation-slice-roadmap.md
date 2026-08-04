# SEDAR Demonstration Implementation Slice Roadmap

| Item | Value |
| --- | --- |
| Solution | SEDAR Integrated ERP and Marine Fleet Management System |
| Platform | Odoo 19 Community and PostgreSQL through Docker |
| Roadmap status | Planning baseline for approval |
| Scope | Demonstration system, not production deployment |
| Active implementation | `sedar-new/` |
| Requirements baseline | `docs/project-requirements.md` version 1.0 |
| Current-status baseline | `docs/implementation-status.md`, assessed 2026-08-05 |

## 1. Purpose

This roadmap divides the remaining SEDAR demonstration work into 15 dependency-ordered implementation slices. Each slice must produce a coherent, testable business outcome and preserve the existing Service Order, Marine Operation, Billing Review, recruitment, crewing, portal, and Document Control workflows.

The roadmap is intentionally more specific than a feature list. It identifies ownership, module boundaries, handoffs, acceptance criteria, demo data, security, and regression expectations so the team can implement one slice at a time without losing the behavior of the whole system.

This document does not approve unconfirmed SEDAR policies. Exact payroll rules, labor policies, maintenance intervals, risk matrices, procurement limits, tariff formulas, stock valuation, and KPI formulas remain demonstration assumptions until validated with SEDAR.

## 2. Source-of-Truth Order

Implementation decisions must be checked in this order:

1. Accepted ADRs define architectural constraints.
2. `CONTEXT.md` defines canonical marine terms.
3. `docs/project-requirements.md` defines demonstration requirements.
4. Current Odoo code defines existing behavior.
5. `docs/custom-models.md` defines current custom model contracts.
6. This roadmap defines the intended delivery sequence.

If these sources disagree, implementation must stop at the affected decision. The team must agree whether to change the requirement, glossary, code, or architecture. An accepted ADR must be superseded by a new numbered ADR rather than silently contradicted.

## 3. Current Baseline

The demonstration currently supports these connected flows:

```text
Client / Customer Relations
  -> Service Order and Confirmed Rate
  -> Tug and crew planning
  -> Dispatch Readiness Gate
  -> Marine Operation
  -> Tug Completion and Service Completion
  -> Billing Review
  -> Draft Odoo customer invoice
  -> Standard invoice posting and payment

Service Order crew shortage
  -> Root-cause review
  -> Manpower request and approval
  -> Vacancy and Careers publication
  -> ADM-3 application
  -> Applicant portal and HR processing
  -> Interview and ADM-4
  -> ADM-5 employment requirements
  -> Odoo employee conversion
```

The first chain is materially complete for demonstration purposes. The second chain reaches employee creation, but it does not yet complete employee onboarding, marine crew onboarding, credential activation, deployment eligibility, or auditable closure of the underlying staffing demand.

## 4. Known Discrepancies to Resolve

### 4.1 Demo records are not fully repeatable

Some post-install hooks create records only when a module is first installed. A reused database can therefore differ from a clean database after module upgrades. Slice 1 must establish idempotent, fictional demo scenarios that can be verified after a fresh installation and safely reconciled on upgrade.

### 4.2 Opening a vacancy currently resolves the crew shortage

`sedar.manpower.request.action_open_vacancies()` currently marks linked shortages resolved as soon as the vacancy is created. Opening a position does not make a Service Order crew-ready and does not prove the staffing demand has been filled.

The corrected planning rule is:

- A Service Order shortage is resolved only by a concrete operational outcome, such as assigning a qualified replacement, rescheduling, cancelling the need, or restoring the unavailable crew member.
- A manpower request and vacancy track longer-term staffing demand independently.
- A filled vacancy closes the approved headcount demand only after the successful applicant becomes an employee and, for a marine role, becomes deployment-eligible crew.

This semantic change must be agreed before Slice 5 or Slice 6 implementation. Because it changes a cross-module workflow in a potentially surprising way, the implementation should include an ADR if the team accepts it.

### 4.3 Recruitment skips explicit control points

The current system can move from completed interview to ADM-5 requirements and employee conversion. ADM-4A Background Inquiry and the Company Interview Orientation Form exist in Document Control, but no recruitment workflow invokes them. There is also no explicit hiring decision or accepted-offer record.

Slices 3 and 4 fill these gaps without claiming that the exact sequence is SEDAR policy. Before implementation, HR terminology and mandatory versus optional gates must be confirmed for the demonstration.

### 4.4 Employee conversion does not finish crew readiness

Odoo employee creation does not automatically create a complete Crew Profile, credentials, medical validity, assignment eligibility, or home-tug relationship. Slices 5 through 7 make that handoff explicit.

### 4.5 Inventory readiness is temporary

ADR-0002 permits an audited manual Inventory Readiness Confirmation for the current MVP. Slice 11 replaces it with stock-derived readiness while preserving the rest of the automated Dispatch Readiness Gate.

## 5. Architectural Invariants

Every slice must preserve these rules:

- One Service Order represents one billable tug assist or move at one Terminal.
- One Ready Service Order creates exactly one Marine Operation.
- The system, not a human Dispatcher role, determines readiness from authoritative tugboat, crew, certificate, and inventory facts.
- Every active tug assignment requires Tug Completion before Service Completion.
- Service Completion is separate from Billing Status.
- SEDAR modules own Service Completion, Client Tariff selection, Billing Review, Billing Adjustments, and draft-invoice handoff.
- Standard Odoo Accounting owns invoices, ledger entries, receivables, payments, reconciliation, and credit notes.
- HR owns the employee record. Crewing owns marine deployment eligibility, rank, rotation, and credential readiness.
- Document Control owns controlled templates, requests, versions, evidence, review, approval, and expiry metadata. Owning departments remain responsible for the business meaning of their documents.
- Portal access must be ownership-based and must exclude internal HR, cost, safety, and management information.
- Demo fixtures must be fictional, deterministic, and separable from production-oriented models.

## 6. Delivery Gate Applied to Every Slice

A slice is complete only when all applicable conditions pass:

1. Canonical terms and unresolved business assumptions are documented before code changes.
2. New models and inherited fields are documented in `docs/custom-models.md` in the same change.
3. Security groups, access rights, record rules, and server-side action authorization are implemented.
4. Required fields, state transitions, duplicate prevention, and cross-record consistency are validated server-side.
5. Fictional happy-path and relevant exception fixtures are installed through a dedicated demo addon or idempotent bootstrap.
6. The shared Docker setup installs or upgrades every required module without manual Apps-screen intervention.
7. Automated tests cover domain rules and handoffs. Portal and dashboard behavior receives manual viewport verification where automated UI coverage is impractical.
8. Existing Service Order-to-payment and shortage-to-employment regression scenarios still pass.
9. The implementation status and affected user/demo documentation are updated.
10. The user manually verifies the slice against its acceptance scenario before the team proceeds.

## 7. Dependency Sequence

```text
1. Repeatable baseline
  -> 2. Recruitment dashboard
  -> 3. Background and orientation controls
  -> 4. Hiring decision and offer
  -> 5. Employee onboarding
  -> 6. Marine crew onboarding
  -> 7. Credentials and medical renewal
  -> 8. Leave, training, and temporary relief
  -> 9. Crew rotation and Service Order scheduling
  -> 10. Technical maintenance
  -> 11. Inventory and fuel
  -> 12. Procurement
  -> 13. HSSE
  -> 14. Broader ERP demonstrations
  -> 15. Corporate documents and executive dashboard
```

Slices 1 through 9 complete the HR, recruitment, crewing, and Service Order staffing story. Slices 10 through 13 replace readiness placeholders and introduce the operational sources required for credible cross-functional reporting. Slice 14 demonstrates remaining standard ERP areas. Slice 15 is last because reliable executive indicators require governed source records from the preceding slices.

## 8. Slice 1: Repeatable Demonstration Baseline

### Outcome

A clean Docker installation and a supported module upgrade produce the same named fictional scenarios for Service Orders, tugboats, crew, shortages, vacancies, applicants, interviews, requirements, Marine Operations, and billing.

### Scope and module ownership

- Retain production-oriented records in their existing functional addons.
- Add recruitment fixtures to a dedicated non-application demo addon, proposed as `sedar_recruitment_demo`.
- Let `sedar_recruitment_demo` depend on `sedar_recruitment_operations`, `sedar_manpower_planning_demo`, and the existing marine demo addons.
- Keep demo credentials and clearly fictional names documented in the shared README.
- Use stable external identifiers and idempotent reconciliation. Do not delete or overwrite unrelated user-created records on upgrade.

### Required scenarios

- New application awaiting review
- Qualified applicant awaiting interview
- Scheduled interview awaiting confirmation
- Reschedule requested
- Completed interview awaiting decision
- Applicant with pending ADM-5 requirements
- Applicant with verified requirements
- Rejected and withdrawn applications
- Successful converted employee
- Permanent headcount shortage linked to manpower request, vacancy, and applicant
- Leave, medical, and certificate shortage examples that do not create permanent vacancies

### Acceptance gate

- Fresh installation creates all named scenarios once.
- Re-running module upgrade creates no duplicates and preserves deliberate user edits outside managed fixture fields.
- Every demo record can be traced backward and forward through its source relationships.
- All existing custom addons install through the shared Docker command.
- Requirement coverage: PLT-001, PLT-002, PLT-005, NFR-007, NFR-010.

## 9. Slice 2: Recruitment Operations Dashboard

### Outcome

HR can understand and operate the recruitment pipeline from one role-focused dashboard without searching unrelated menus.

### Scope and module ownership

- Extend `sedar_recruitment_operations`; reuse `hr.applicant`, `sedar.job.vacancy`, `sedar.applicant.interview`, and `sedar.document.request` as source records.
- Prefer saved domains, grouped list/pivot/graph views, and Odoo actions over duplicating transactional data into dashboard tables.
- Any aggregate helper must be computed from authoritative records and support drill-down.

### Dashboard content

- Open vacancies, approved openings, filled openings, and remaining openings
- Applicants by internal stage and applicant-visible status
- Unassigned applications
- Overdue HR actions and review deadlines
- Interviews today, upcoming, reschedule requested, no-show, and awaiting appraisal
- Employment requirements awaiting applicant submission, HR review, or approval
- Applications awaiting decision, onboarding, or employee conversion
- Recent hires, rejections, and withdrawals

### Security and privacy

- HR users see recruitment data according to standard Odoo Recruitment access plus SEDAR rules.
- Interviewers see only assigned interviews and required appraisal records unless they also hold HR roles.
- Sensitive attachments and internal rejection/background notes never appear in applicant portal responses.

### Acceptance gate

- Every count opens the exact filtered source records that produced it.
- The dashboard renders meaningful data from Slice 1 on a fresh database.
- Applicant portal ownership and client portal isolation remain unchanged.
- Requirement coverage: HR-002, HR-003, HR-004, HR-008, PLT-003, PLT-004, NFR-005.

## 10. Slice 3: Background Inquiry and Orientation Controls

### Outcome

Recruitment can invoke, track, and complete ADM-4A Background Inquiry and Company Interview Orientation using the approved Document Control catalogue rather than disconnected files.

### Terminology and policy checkpoint

Before implementation, agree whether each control is mandatory, who completes it, when it occurs, what the applicant may see, and whether an adverse result blocks hiring. Record agreed canonical terms if they will appear across modules.

### Scope and module ownership

- Extend `sedar_recruitment_operations` and the existing `sedar.document.request` recruitment integration.
- Reuse the approved ADM-4A and orientation Document Types and their complete source content.
- Add only recruitment coordination fields that cannot be derived from requests, such as gate applicability, responsible user, due date, and summarized outcome.
- Keep detailed confidential background responses in access-controlled Document Requests.

### Workflow

```text
Interview appraisal reviewed
  -> determine required checks
  -> create controlled request(s)
  -> complete and submit
  -> HR review
  -> approve, return, or reject
  -> release or block hiring decision
```

### Acceptance gate

- Requests are generated from the approved catalogue with the correct applicant and purpose.
- Required checks block the next stage until approved; optional checks do not.
- Confidential content is available only to authorized HR reviewers.
- Applicant-visible status communicates progress without exposing internal findings.
- Requirement coverage: HR-002, HR-005, DOC-002, DOC-003, DOC-006, PLT-003, PLT-004.

## 11. Slice 4: Hiring Decision and Offer

### Outcome

The system records an explicit, auditable decision after evaluation and requires an accepted offer before employment requirements can lead to employee conversion.

### Terminology and policy checkpoint

Agree the meanings and permitted transitions for Hiring Decision, Conditional Offer, Offer Issued, Accepted, Declined, Expired, and Withdrawn. Compensation fields and approval authority must remain demonstration-only until SEDAR confirms policy.

### Proposed model boundary

- Add a dedicated recruitment-owned offer/decision record, proposed as `sedar.applicant.offer`, instead of overloading applicant stages or Document Requests.
- Link it to one applicant, vacancy, job, decision authority, proposed start date, employment type, offer version, state, and optional controlled attachment.
- Restrict compensation and internal decision rationale to authorized HR management.
- Preserve previous offer versions rather than silently overwriting issued terms.

### Workflow

```text
Evaluation controls cleared
  -> HR recommendation
  -> authorized decision
  -> offer prepared and issued
  -> applicant accepts, declines, or requests clarification
  -> accepted offer permits ADM-5 requirements
```

### Acceptance gate

- A rejected or uncleared applicant cannot receive an offer.
- Issuing and accepting an offer record actor and timestamp.
- Applicant portal exposes only approved offer content and permitted actions.
- Employee conversion is blocked without one active accepted offer.
- Declined/expired offers update vacancy availability without deleting history.
- Requirement coverage: HR-001, HR-002, HR-003, PLT-004, NFR-004, NFR-006.

## 12. Slice 5: Applicant-to-Employee Onboarding

### Outcome

A successful applicant becomes a usable Odoo employee with traceable source data, onboarding responsibilities, and correct vacancy/headcount status.

### Scope and module ownership

- Extend `sedar_recruitment_operations` for generic employee conversion and onboarding.
- Continue to use standard `hr.employee`, `hr.department`, and `hr.job` as HR truth.
- Reuse Odoo's existing applicant-to-employee relationship where sufficient; add reverse or audit fields only when absent.
- Introduce an onboarding checklist record only if standard activities cannot provide status, evidence, ownership, and reusable templates.

### Data handoff

- Transfer approved identity/contact data without replacing employee-owned edits on later updates.
- Link the employee to source applicant, vacancy, accepted offer, and approved ADM-5 request.
- Assign department, job, manager, employment type, and planned start date.
- Preserve application, offer, and requirement history as read-only recruitment evidence.
- Convert portal access according to an agreed identity policy without exposing internal employee fields.

### Vacancy and manpower behavior

- Derive filled openings from completed employee conversions linked to the vacancy, or update them through one idempotent audited hiring action.
- Close a vacancy only when all approved openings are filled or HR explicitly closes it with a reason.
- Close the manpower demand when its approved openings are fulfilled, not when the vacancy is merely published.
- Do not automatically claim that an original Service Order shortage was operationally resolved by the hire.

### Acceptance gate

- Duplicate employee creation from the same applicant is prevented.
- An accepted offer and approved ADM-5 are required.
- Vacancy and manpower counts update exactly once.
- Employee and applicant histories remain mutually traceable.
- Non-marine hires stop here without receiving a Crew Profile.
- Requirement coverage: HR-001, HR-002, HR-005, HR-008, PLT-001, PLT-004.

## 13. Slice 6: Marine Crew Onboarding

### Outcome

An employee hired for a marine position can become a Crew Profile with rank, home tugboat, credential requirements, and a controlled deployment-eligibility state.

### Module boundary

- Add an integration addon, proposed as `sedar_recruitment_crewing`, depending on recruitment operations, manpower planning, and marine operations.
- Do not make generic HR recruitment own marine readiness rules.
- Reuse existing `sedar.crew.profile`, rank, certificate type, manning template, and employee relationships.

### Workflow

```text
Employee created for marine vacancy
  -> create crew onboarding case
  -> assign rank and identifiers
  -> determine required certificates and medical
  -> assign home tugboat when appropriate
  -> collect and verify evidence
  -> mark deployment-eligible only when all mandatory checks pass
```

### Cross-module behavior

- The originating vacancy and manpower demand point to the resulting employee and Crew Profile.
- Deployment eligibility is computed from Crewing facts, not manually copied into HR.
- A new Crew Profile does not automatically join an active Service Order; Operations must make a dated assignment.
- An operational shortage closes only when its concrete assignment or other resolution is recorded.

### Acceptance gate

- Marine and non-marine onboarding follow separate paths.
- Missing rank, medical, or required credentials blocks deployment eligibility with an explanation.
- A qualified profile becomes selectable for compatible assignments.
- Hiring traceability remains visible from Service Order/manpower evidence through vacancy, applicant, employee, and Crew Profile.
- Requirement coverage: CRW-001, CRW-003, CRW-004, HR-001, HR-008, OPS-003.

## 14. Slice 7: Crew Credentials and Medical Renewal

### Outcome

Certificate and medical records have controlled evidence, expiry visibility, renewal actions, and an authoritative effect on crew readiness.

### Module boundary

- Add or extend a focused crewing compliance addon, proposed as `sedar_crew_compliance`.
- Crewing owns certificate and medical facts; Document Control owns attached evidence, version, review, and approval.
- Avoid storing the same expiry date independently in both modules. One authoritative validity record should drive Document Control views and readiness.

### Capability

- Certificate number, type, issuing authority, issue date, expiry date, verification state, evidence, and superseded version
- Medical provider, examination date, fitness result, restrictions, validity, and evidence
- Renewal case with owner, due date, state, replacement record, and reminders
- Exception views for expired, expiring, missing, rejected, and renewal-in-progress records
- Rank/service/tug-class requirement matching using existing manning rules

### Acceptance gate

- Expired or rejected evidence blocks readiness immediately.
- Approved renewal restores readiness without deleting historical records.
- Expiry dashboards drill down to the authoritative crew and document records.
- Portal exposure is explicitly denied unless a later employee self-service rule allows it.
- Requirement coverage: CRW-003, CRW-004, DOC-003, DOC-005, HSE-007, OPS-003.

## 15. Slice 8: Leave, Training, and Temporary Relief

### Outcome

Crewing can distinguish and resolve temporary availability shortages without incorrectly creating permanent vacancies.

### Module boundary

- Add a crewing availability addon, proposed as `sedar_crewing_availability`.
- Integrate standard Odoo Time Off (`hr_holidays`) for approved leave where available.
- Keep compliance training requirements connected to Slice 7 and later HSSE training, without duplicating employee records.
- Reuse `sedar.crew.shortage.action` for explicit resolution actions, extending it only where required.

### Workflow paths

- Approved leave creates dated unavailability and a replacement/reschedule path.
- Medical restriction creates dated or open-ended unavailability managed by authorized HR/Crewing roles.
- Required training creates a scheduled action and may block deployment until completed.
- Temporary relief selects a qualified available Crew Profile for a dated assignment.
- Permanent manpower escalation is permitted only when root-cause review confirms actual headcount demand.

### Acceptance gate

- Leave, medical, training, temporary relief, and permanent headcount examples produce visibly different actions.
- Availability starts and ends from source dates rather than a permanently toggled manual state.
- Temporary relief checks rank, credentials, medical, schedule, and existing assignments.
- Completing a non-hiring action resolves only the affected shortage and records evidence/outcome.
- Requirement coverage: CRW-004, CRW-005, CRW-007, OPS-003, HR-008.

## 16. Slice 9: Crew Rotation and Service Scheduling

### Outcome

Operations and Crewing share a dated schedule that shows whether each tugboat and Service Order has sufficient qualified crew without overlapping assignments.

### Module boundary

- Add a scheduling addon, proposed as `sedar_crew_scheduling`, depending on marine operations, dispatch, and crewing availability.
- Crew assignment records remain the transactional truth. Calendar, timeline, and dashboard views are presentations of those records.
- Do not introduce a human Dispatch approval that contradicts ADR-0002.

### Capability

- Rotation period, watch/shift when known, home tug, relief crew, handover date, and assignment state
- Calendar or timeline by tugboat, Crew Profile, and Service Order
- Conflict checks for overlapping active assignments and leave/unavailability
- Coverage checks against manning template ranks and certificates
- Suggested eligible replacements as decision support, never silent auto-assignment
- Upcoming Service Order readiness forecast and unresolved staffing blockers

### Acceptance gate

- Overlapping crew assignments are rejected or explicitly resolved.
- A planned future assignment respects dated leave and credential expiry at service time.
- Operations sees the exact missing rank or compliance requirement.
- A corrected assignment causes the existing automated readiness computation to reevaluate.
- Requirement coverage: OPS-002, OPS-003, CRW-002, CRW-005, CRW-007.

## 17. Slice 10: Technical Maintenance Foundation

### Outcome

Maintenance becomes the authoritative source of tugboat technical availability and demonstrates planned and corrective work with equipment history.

### Module boundary

- Add `sedar_marine_maintenance` on top of standard Odoo Maintenance where the Community edition supports the required behavior.
- Extend standard equipment and maintenance requests for marine relationships rather than building an unrelated maintenance database.
- Link equipment to tugboat, parent equipment/system, criticality, installation dates, and history.
- Keep spare-part reservation as a visible pending integration until Slice 11.

### Workflow

```text
Planned interval due or defect reported
  -> maintenance/work order
  -> assess priority and tug availability impact
  -> plan labor, parts, and dates
  -> perform and verify work
  -> update equipment history
  -> release maintenance hold
```

### Acceptance gate

- Planned maintenance can generate or schedule work by date or representative running interval.
- A defect progresses from report through verified closure.
- A critical open work order or maintenance hold blocks tugboat readiness.
- Closing verified work restores availability only when no other blocking condition exists.
- Dry-dock plan and milestones are represented without inventing regulatory intervals.
- Requirement coverage: MNT-001 through MNT-006, OPS-003, PLT-004.

## 18. Slice 11: Inventory, Spare Parts, Fuel, and Lubricants

### Outcome

Standard stock records replace manual Inventory Readiness Confirmation and provide traceable parts and fuel facts for maintenance, operations, and later profitability.

### Module boundary

- Add `sedar_marine_inventory` on standard Odoo Inventory (`stock`).
- Use standard products, units, warehouses, locations, lots where needed, receipts, transfers, issues, returns, and adjustments.
- Add marine references only where standard stock moves cannot express tugboat, Marine Operation, Service Order, tank, or work-order context.
- Keep historical manual confirmations visible for audit, but stop using them for new readiness decisions after controlled migration.

### Capability

- Main warehouse and tugboat/vessel stock locations
- Spare parts, fuel, lubricants, consumables, and office supplies
- Reorder rules and visible shortages
- Parts reservation and consumption against maintenance work orders
- Fuel receipt, transfer, issue, operation consumption, and remaining balance
- Inventory requirement lines associated with Service Order/service type where justified
- Barcode-ready product identifiers and one representative scan flow if the installed edition supports it

### Acceptance gate

- Authoritative available stock computes the inventory component of the Dispatch Readiness Gate.
- A relevant Service Order change invalidates and recomputes stock readiness.
- A work order shows requested, reserved, issued, and consumed parts.
- A Marine Operation shows traceable opening, issued, consumed, and remaining fuel facts.
- Existing crew and tug readiness behavior remains automated.
- Requirement coverage: INV-001 through INV-006, OPS-003, OPS-007, MNT-004, MGT-002.

## 19. Slice 12: Procurement Handoff

### Outcome

An approved maintenance or stock demand can be followed through Purchase Request, approval, standard Purchase Order, receipt, stock availability, supplier bill, and payment foundation.

### Module boundary

- Add a focused Purchase Request addon, proposed as `sedar_purchase_request`, because Odoo Community does not provide SEDAR's requested departmental request/approval record by default.
- Use standard Odoo Purchase for requests for quotation and Purchase Orders, Inventory for receipts, and Accounting for supplier bills.
- Do not create custom purchase orders, receipts, bills, or accounting entries.

### Workflow

```text
Maintenance or reorder shortage
  -> Purchase Request
  -> configurable demo approval
  -> standard RFQ / Purchase Order
  -> standard receipt
  -> stock availability update
  -> standard supplier bill
```

### Acceptance gate

- Request lines retain their maintenance or inventory source.
- Approval authority is enforced server-side and recorded with time.
- An approved request creates or links a standard Purchase Order without duplicate lines.
- Receipt updates the same product/location facts consumed by readiness and maintenance.
- Supplier bill remains standard Odoo Accounting truth under ADR-0001's general ledger boundary.
- Requirement coverage: PRC-001 through PRC-005, FIN-003, INV-001, INV-002, MNT-004.

## 20. Slice 13: HSSE and Operational Compliance

### Outcome

SEDAR can demonstrate incidents, near misses, inspections, risk assessments, permits, corrective actions, meetings, and training linked to operations, people, tugboats, and controlled evidence.

### Module boundary

- Add `sedar_hsse` as the authoritative HSSE workflow addon.
- Link to Service Order, Marine Operation, tugboat, employee/Crew Profile, Terminal, maintenance work order, and controlled documents without copying their master data.
- Use a shared corrective-action model across incidents, inspections, risks, and audits when the lifecycle and security are genuinely identical.

### Capability

- Incident and near-miss classification, severity, people, location, evidence, investigation, and closure
- Checklist inspections with findings
- Risk assessment with hazard, controls, likelihood, impact, residual risk, owner, and approval
- Permit validity and operational applicability
- Corrective actions with owner, due date, evidence, overdue status, and verification
- Safety meetings, attendance, topics, and actions
- HSSE training requirements and completion linked to crew readiness where applicable

### Acceptance gate

- One incident progresses through investigation and verified closure.
- One inspection creates an assigned overdue finding.
- Expired required permit or critical unresolved safety control produces a visible operational exception according to an explicitly approved demo rule.
- HSSE portal exposure excludes confidential investigation details.
- Requirement coverage: HSE-001 through HSE-007, DOC-003, DOC-005, MGT-004.

## 21. Slice 14: Broader Standard ERP Demonstrations

### Outcome

The remaining requested Finance, HR, and Customer Management capabilities are visible through representative standard Odoo workflows or clearly labeled demonstration extensions.

This is a program slice and should be executed internally in the following order so each sub-slice remains testable.

### 14A. HR operations

- Install/configure standard Attendance and seed representative check-in/out records.
- Demonstrate employee performance evaluation and review history. Check module availability and licensing before choosing standard Odoo Appraisals; use a thin custom demo model only if the shared Odoo edition does not provide it.
- Expose employee self-service information appropriate to portal/internal access.
- Produce payroll-input facts from attendance, leave, and eligible crew assignments, but do not claim validated Philippine payroll calculation.

### 14B. Finance demonstrations

- Configure representative journals and show General Ledger entries from posted customer and supplier invoices.
- Add a sample department or vessel budget and budget-versus-actual view.
- Show sample cash position/inflow/outflow using standard accounting facts.
- Configure a representative tugboat or equipment fixed asset and depreciation.
- Add one bank reconciliation example if the installed Odoo edition supports the needed standard flow.
- Preserve standard Odoo Accounting ownership and avoid a custom ledger.

### 14C. CRM and customer follow-up

- Install/configure standard Odoo CRM.
- Demonstrate one opportunity linked to client, assisted vessel/service interest, follow-up activities, and resulting Service Order.
- Keep the Service Order as the marine request and do not turn CRM opportunity stages into operational states.

### Acceptance gate

- Each sub-slice is clearly labeled demonstration-only where SEDAR policy or statutory validation is missing.
- Shared employee, partner, invoice, payment, product, and Service Order records are reused without duplicate masters.
- Portal rules continue to exclude internal HR, cost, and safety data.
- Requirement coverage: HR-006, HR-007, CRW-006, FIN-001, FIN-003 through FIN-008, MKT-001 through MKT-004.

## 22. Slice 15: Corporate Documents and Executive Dashboard

### Outcome

Leadership can see the requested cross-functional system as one coherent organization, with every KPI and exception drilling down to governed Odoo source records.

### 15A. Corporate and controlled document coverage

- Add representative contracts, vessel certificates, insurance policies, permits, board resolutions, ISO documents, legal cases, and internal-audit records.
- Preserve the approved source file and complete visible content where a source form exists.
- Add owner, status, validity, renewal, approval, attachment, confidentiality, and related business object as appropriate.
- Build a unified expiry/renewal view from authoritative document and credential validity facts.

### 15B. Executive dashboard

- Revenue, invoiced, unpaid, and cash indicators from standard Accounting
- Service volume and operational status from Service Orders and Marine Operations
- Fleet utilization from approved actual-time formulas
- Tugboat availability and blocker reasons from Operations and Maintenance
- Staffing, vacancies, hires, shortages, and credential expiry from HR and Crewing
- Maintenance due, defects, downtime, and dry-dock status
- Inventory shortages and fuel usage
- Procurement cycle and overdue request indicators
- HSSE incidents, high risks, permits, and overdue corrective actions
- Document expiry and governance exceptions
- Profitability only when attributable fuel, labor, parts, and approved cost rules exist; otherwise show revenue and known cost separately

### 15C. Future integration visibility

- Show clearly labeled connection status and sample timestamped data contracts for Power BI, AIS/GPS, Microsoft 365, DocuSign, barcode devices, or bank feeds.
- Do not present mock data as a live integration.

### Acceptance gate

- Every KPI identifies its formula, authoritative source model, date basis, filters, and drill-down action.
- No manually typed dashboard total competes with transactional source records.
- Executive access does not bypass departmental record rules without an explicitly approved role.
- The 12 demonstration acceptance scenarios in the PRD can be presented in one prepared walkthrough.
- Requirement coverage: DOC-001 through DOC-007, MGT-001 through MGT-005, MGT-002 only to the level supported by approved cost sources.

## 23. Cross-Module Ownership Matrix

| Record or fact | Authoritative owner | Consumers | Rule |
| --- | --- | --- | --- |
| Applicant and recruitment stage | HR / Odoo Recruitment | Careers, portal, documents, onboarding | Portal sees controlled public status only. |
| Hiring decision and offer | HR | Applicant portal, onboarding | Restricted terms and versioned decisions. |
| Employee | HR / `hr.employee` | Crewing, maintenance labor, HSSE, payroll input | Do not create a separate employee master. |
| Crew Profile and deployment eligibility | Crewing | Service Order readiness, scheduling, HSSE | Employee creation alone does not imply readiness. |
| Credential and medical validity | Crewing with Document Control evidence | Readiness, scheduling, HR, HSSE | One authoritative validity fact. |
| Leave | HR Time Off | Crewing availability, scheduling | Dated approved leave drives temporary unavailability. |
| Service Order | Customer Relations / Marine Operations | Dispatch, crewing, billing, portal, KPIs | One billable assist or move at one Terminal. |
| Marine Operation and actual time | Operations | Billing, fuel, HSSE, KPIs | Created only from Ready Service Order. |
| Tugboat technical availability | Maintenance | Dispatch readiness, scheduling, KPIs | No independent manual copy after Slice 10. |
| Product and stock quantity | Odoo Inventory | Readiness, maintenance, procurement, costing | Stock movement is the quantity truth. |
| Purchase Order and receipt | Odoo Purchase / Inventory | Procurement, Finance, Maintenance | Custom Purchase Request only governs demand and approval. |
| Invoice, payment, and ledger | Odoo Accounting | Billing Status, cash, management | ADR-0001 boundary applies. |
| Incident, risk, and corrective action | HSSE | Operations, training, management | Sensitive investigation access is restricted. |
| Controlled document | Document Control and owning department | HR, Crewing, Technical, HSSE, corporate | Evidence and version history are preserved. |

## 24. End-to-End Regression Matrix

The following scenarios must remain valid as slices are added:

| Scenario | Must be rechecked after |
| --- | --- |
| Client creates and sees only its own Service Order | Every portal, CRM, dashboard, or security change |
| Confirmed Rate remains frozen and tariff revisions remain auditable | Finance, Service Order, and dashboard changes |
| Ready order creates exactly one Marine Operation | Crewing, Maintenance, Inventory, and HSSE readiness changes |
| Multi-tug Service Completion requires every active Tug Completion | Dispatch, operation, and Finance changes |
| Billing Review uses actual quantities and creates one draft standard invoice | Inventory cost, procurement, and Finance changes |
| Non-headcount shortage does not create a permanent vacancy | Slices 5 through 9 |
| Vacancy traces to manpower evidence and applications | Slices 1 through 6 |
| Applicant sees only owned portal-safe records | Every HR and Document Control change |
| Employee conversion is idempotent and preserves recruitment history | Slices 4 through 7 and Slice 14 |
| Marine hire is not assignable until qualified | Slices 6 through 9 and Slice 13 |
| Maintenance hold blocks tugboat readiness | Slices 10 through 13 |
| Stock shortage blocks only the inventory component of readiness | Slices 11 through 13 |
| Purchase receipt updates the same stock facts used by readiness | Slices 11 and 12 |
| Executive totals drill down to governed source records | Slices 14 and 15 |

## 25. Requirement Traceability by Slice

| Slice | Primary requirement groups |
| --- | --- |
| 1 | PLT-001, PLT-002, PLT-005, NFR-007, NFR-010 |
| 2 | HR-002, HR-003, HR-004, HR-008, dashboard requirements |
| 3 | HR-002, HR-005, DOC-002, DOC-003, DOC-006 |
| 4 | HR-001, HR-002, HR-003, PLT-004 |
| 5 | HR-001, HR-002, HR-005, HR-008 |
| 6 | CRW-001, CRW-003, CRW-004, OPS-003 |
| 7 | CRW-003, CRW-004, DOC-003, DOC-005, HSE-007 |
| 8 | CRW-004, CRW-005, CRW-007 |
| 9 | OPS-002, OPS-003, CRW-002, CRW-005 |
| 10 | MNT-001, MNT-002, MNT-003, MNT-004, MNT-005, MNT-006 |
| 11 | INV-001, INV-002, INV-003, INV-004, INV-005, INV-006, OPS-007, MNT-004 |
| 12 | PRC-001, PRC-002, PRC-003, PRC-004, PRC-005, FIN-003 |
| 13 | HSE-001, HSE-002, HSE-003, HSE-004, HSE-005, HSE-006, HSE-007 |
| 14 | HR-006, HR-007, CRW-006, FIN-001, FIN-003, FIN-004, FIN-005, FIN-006, FIN-007, FIN-008, MKT-003 |
| 15 | DOC-004, DOC-005, DOC-007, MGT-001, MGT-002, MGT-003, MGT-004, MGT-005, OPS-009 and all dashboard requirements |

The following requirements are already represented in the baseline and are protected by the regression matrix rather than scheduled as replacement builds: FIN-002, FIN-009, FIN-010, OPS-001, OPS-004, OPS-005, OPS-006, OPS-008, MKT-001, MKT-002, and MKT-004. Existing Document Control behavior also remains the foundation for DOC-001, DOC-002, DOC-003, and DOC-006.

All slices inherit PLT-003, PLT-004, NFR-001, NFR-002, NFR-003, NFR-004, NFR-005, NFR-006, NFR-007, NFR-008, NFR-009, NFR-010, and relevant portal/privacy requirements.

## 26. Decisions Required Before Their Slices

These questions must not block earlier independent slices, but each must be resolved before its affected implementation begins:

| Before slice | Required decision |
| --- | --- |
| 3 | Whether background inquiry and orientation are mandatory, their order, owner, visibility, and blocking result |
| 4 | Hiring-decision authority, offer states, acceptance method, expiry, and sensitive compensation access |
| 5 | Employee portal identity transition, onboarding checklist ownership, and vacancy fill definition |
| 6 | Definition of deployment-eligible crew and who authorizes it |
| 7 | Credential requirement matrix, expiry warning windows, verifier, and medical privacy rules |
| 8 | Leave approval source, temporary-relief policy, training blocker rules, and return-to-duty authority |
| 9 | Rotation pattern, watch structure, assignment authority, and overlap exceptions |
| 10 | Maintenance intervals, equipment hierarchy, criticality, dry-dock rules, and release authority |
| 11 | Warehouse/location structure, stock policy, fuel units, tanks, consumption evidence, and valuation approach |
| 12 | Procurement approval levels, supplier qualification, receiving responsibilities, and three-way-match expectation |
| 13 | HSSE classifications, risk matrix, escalation thresholds, confidentiality, and operational blocking rules |
| 14 | Attendance method, appraisal criteria, payroll-input scope, budget structure, chart of accounts, and CRM handoff |
| 15 | KPI formulas, target values, profitability allocation, executive access, and document retention/renewal policy |

Until confirmed, each slice should use a clearly labeled fictional configuration that can be replaced without changing the core model architecture.

## 27. Slice Execution Procedure

For each slice, the team will follow this sequence:

1. Re-read `CONTEXT.md`, relevant ADRs, the PRD requirements, `docs/custom-models.md`, current manifests, and affected code.
2. Resolve the slice-specific decisions listed above.
3. Produce a field/model delta and data-flow sketch before implementation.
4. Confirm whether a new ADR is required.
5. Implement the smallest module boundary that owns the business behavior.
6. Update `docs/custom-models.md`, implementation status, Docker bootstrap, seed data, and demo instructions in the same change.
7. Run module installation/upgrade, automated tests, security checks, and the regression matrix.
8. Perform the slice's manual acceptance walkthrough with the approved demo accounts.
9. Fix all failed acceptance criteria before starting the next slice.
10. Commit and push only the verified slice with a message that identifies its demonstration scope.

## 28. Recommended Immediate Work

Begin with Slice 1 only. Its detailed implementation plan should identify the exact fixture records, stable external identifiers, idempotent update policy, dependencies, expected counts, and clean-install verification commands.

After Slice 1 passes its acceptance gate, execute Slice 2. Do not begin background checks, offers, or onboarding until the recruitment dashboard consistently exposes the baseline records and relationships they will extend.

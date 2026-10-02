# SEDAR Demonstration Realignment Report: Slices 1-9

| Item | Value |
| --- | --- |
| Assessment date | 2026-08-05 |
| Branch | `sedar-new` |
| Assessed head | `66e4c59` |
| Active implementation | `sedar-new/` Odoo 19 Docker stack |
| Roadmap | `sedar-planning/implementation-slice-roadmap.md` |
| Requirements baseline | `docs/project-requirements.md` |
| Architecture constraints | ADR-0001, ADR-0002, and ADR-0003 |

## 1. Executive Conclusion

The implementation remains aligned with the approved demonstration roadmap and the SEDAR requirements. Slices 1 through 9 now form one connected demonstration from Service Order staffing demand through recruitment, employee conversion, marine crew onboarding, credential control, dated availability, temporary relief, and crew scheduling.

The most important architectural boundaries remain intact:

- A Service Order is still the client request and operational planning aggregate.
- A Ready Service Order still creates exactly one Marine Operation through the automated Dispatch Readiness Gate.
- HR headcount fulfillment remains separate from operational shortage resolution under ADR-0003.
- Employee creation does not make a marine hire deployment eligible.
- Credential validity, dated availability, and schedule conflicts now affect assignment eligibility and Service Order readiness.
- Finance continues to receive completed operational facts and hand off only to standard Odoo Accounting under ADR-0001.

The project should proceed to Slice 10, Technical Maintenance Foundation. Maintenance is now the largest missing operational dependency because tugboat technical availability is still represented by a manually maintained tugboat state rather than authoritative defects and work orders.

## 2. Current End-to-End Demonstration

```text
Client / Customer Relations
  -> Service Order and Confirmed Rate
  -> tugboat and manning plan
  -> qualified crew assignment
       -> headcount shortage -> manpower request -> vacancy -> Careers
       -> applicant -> interview controls -> offer -> ADM-5
       -> employee -> marine crew onboarding -> Crew Profile
       -> verified credentials and medicals
       -> dated leave / training / medical availability
       -> temporary relief and rotation scheduling
  -> Dispatch Readiness Gate
  -> Marine Operation
  -> Tug Completion and Service Completion
  -> Billing Review
  -> draft Odoo customer invoice
  -> standard Odoo posting and payment
```

This flow is cohesive because each fact has one owner. HR owns applicants and employees, Crewing owns Crew Profiles and deployment eligibility, Operations owns concrete Service Order assignments and shortage resolution, Document Control owns controlled evidence, and Odoo Accounting owns the ledger.

## 3. Slice-by-Slice Realignment

| Slice | Status | Implemented result | Alignment assessment |
| --- | --- | --- | --- |
| 1. Repeatable Demonstration Baseline | Implemented | `sedar_recruitment_demo` reconciles named fictional recruitment scenarios using stable links and repeatable bootstrap behavior. | Aligned with PLT-001, PLT-002, PLT-005, NFR-007, and NFR-010. |
| 2. Recruitment Operations Dashboard | Implemented | HR queues and source-record views cover vacancies, applicant stages, interviews, requirements, decisions, and hiring actions. | Aligned with HR-002, HR-003, HR-004, HR-008, and role-based dashboard requirements. |
| 3. Background Inquiry and Orientation Controls | Implemented | Approved ADM-4A and CM-053 catalogue definitions generate confidential controlled requests that gate later recruitment work. | Aligned with HR-002, HR-005, DOC-002, DOC-003, and DOC-006. |
| 4. Hiring Decision and Offer | Implemented | `sedar.applicant.offer` records decision, issue, response, authority, timestamps, and the accepted-offer gate. | Aligned with HR-001, HR-002, HR-003, PLT-004, NFR-004, and NFR-006. |
| 5. Applicant-to-Employee Onboarding | Implemented | Employee conversion is idempotent, source-linked, gated by accepted offer and approved ADM-5, and updates vacancy/manpower fulfillment once. | Aligned with HR-001, HR-002, HR-005, HR-008, and ADR-0003. |
| 6. Marine Crew Onboarding | Implemented | Marine hires receive a crewing-owned onboarding case and become deployable only after rank, tugboat, credential, and medical requirements pass. | Aligned with CRW-001, CRW-003, CRW-004, HR-001, HR-008, and OPS-003. |
| 7. Crew Credentials and Medical Renewal | Implemented for the demonstration, with detail gaps | `sedar_crew_compliance` adds controlled evidence requests, verification, renewal status, expiry exceptions, access control, and readiness effects. | Core acceptance is aligned with CRW-003, CRW-004, DOC-003, DOC-005, HSE-007, and OPS-003. Production-detail fields remain incomplete. |
| 8. Leave, Training, and Temporary Relief | Implemented | `sedar_crewing_availability` adds dated unavailability, approved Time Off synchronization, medical/training blockers, and qualified temporary-relief assignment. | Aligned with CRW-004, CRW-005, CRW-007, OPS-003, HR-008, and ADR-0003. |
| 9. Crew Rotation and Service Scheduling | Implemented for the demonstration, with presentation gaps | `sedar_crew_scheduling` adds assignment dates/status, confirmation controls, replacement suggestions, schedule views, and rotation/handover records with overlap validation. | Core acceptance is aligned with OPS-002, OPS-003, CRW-002, CRW-005, and CRW-007. A consolidated readiness forecast remains future presentation work. |

## 4. What Slices 7-9 Changed

### Slice 7: Credential and medical truth

Before Slice 7, certificate dates existed but their evidence and verification lifecycle were weak. The new addon makes verified and unexpired credential records part of both crew onboarding and Service Order assignment eligibility. Renewal uses a controlled Document Request with auditable requester, reviewer, and timestamps.

Remaining detail gaps:

- Issuing authority is not stored on the base credential record.
- Medical provider, examination date, fitness result, and restrictions are not separate structured fields.
- Renewal evidence is preserved in Document Control, but an explicit superseded credential-version relationship is not modeled.
- The 30-day renewal window is a generic demonstration assumption and reminders are not automated.

These gaps do not break the demonstration's core readiness control, but they must not be presented as production-complete maritime compliance.

### Slice 8: Temporary shortage truth

Before Slice 8, availability was mostly a current status and could not reliably answer whether a person was available for a future Service Order. The new dated unavailability record handles leave, medical, training, temporary, and other blockers. Approved Odoo Time Off creates or updates the related availability blocker.

Temporary relief now creates a concrete crew assignment and resolves only its linked operational shortage. It does not create a vacancy and does not imply permanent headcount fulfillment. This directly satisfies the intent of ADR-0003.

Remaining detail gaps:

- Return-to-duty authority and evidence are represented by workflow state and notes, not a dedicated approval record.
- Training-session planning and attendance remain part of the future HSSE slice.
- Leave and temporary-relief policies use generic demonstration assumptions pending SEDAR confirmation.

### Slice 9: Dated scheduling truth

Before Slice 9, assignment eligibility existed but there was no focused calendar/rotation workflow. Service Order assignment windows now come from the order schedule, confirmation is blocked when eligibility fails, and suggested replacements are filtered by rank, verified credentials, dated unavailability, and assignment conflicts.

Crew rotation records now represent tugboat, period, watch, relief crew, handover, and lifecycle state. Planned and active rotations for the same Crew Profile cannot overlap.

Remaining detail gaps:

- Rotation plans do not silently create or replace Service Order assignments; Operations must make the concrete assignment. This is intentional decision support.
- A single consolidated upcoming-readiness forecast dashboard is not yet present; calendar, list, status, and blocker views provide the underlying demonstration.
- Confirmed SEDAR watch patterns, rotation cycles, handover policy, and overlap exceptions are still unknown.

## 5. Requirements Realignment

### Human Resources and recruitment

| Requirement | Current status | Evidence or remaining work |
| --- | --- | --- |
| HR-001 Employee master | Implemented | Successful applicants convert to standard `hr.employee` records with source links. |
| HR-002 Recruitment lifecycle | Implemented | Vacancy through application, controls, offer, requirements, and employment is demonstrable. |
| HR-003 Applicant tracking and privacy | Implemented | Applicant portal ownership and controlled public statuses exist. |
| HR-004 Interview scheduling and appraisal | Implemented | Calendar-backed interview scheduling and ADM-4 requests exist. |
| HR-005 Typed data and attachments | Implemented | ADM-3, ADM-5, and controlled recruitment forms store typed values and evidence. |
| HR-006 Attendance | Not implemented | Planned for Slice 14 using standard Odoo HR where suitable. |
| HR-007 Performance evaluation | Not implemented | Planned for Slice 14. |
| HR-008 Manpower traceability | Implemented | Shortage, manpower request, vacancy, applicant, and employee links are preserved without falsely resolving Operations. |

### Crewing

| Requirement | Current status | Evidence or remaining work |
| --- | --- | --- |
| CRW-001 Crew Profile linked to employee | Implemented | Marine onboarding creates or links one Crew Profile to the employee. |
| CRW-002 Assignment, manning, and rotation | Implemented for demo | Manning requirements, dated assignments, conflict controls, schedule views, and rotations exist. |
| CRW-003 STCW and certificates | Implemented for demo | Number, issue/expiry dates, controlled evidence, verification, renewal state, and readiness impact exist. |
| CRW-004 Medical validity | Implemented for demo | Medical-classified credential validity and dated medical unavailability block readiness. Structured clinical detail remains deferred. |
| CRW-005 Leave and temporary unavailability | Implemented | Approved Time Off and other dated blockers affect overlapping service windows. |
| CRW-006 Payroll-relevant service facts | Not implemented | Planned for Slice 14 after payroll-input scope is agreed. |
| CRW-007 Shortage cause separation | Implemented | Headcount, leave, medical, certification, training, and temporary-relief paths remain distinct. |

### Connected Operations and Document Control requirements

| Requirement | Current status | Evidence or remaining work |
| --- | --- | --- |
| OPS-002 Tug and crew scheduling | Implemented for demo | Service Order schedule drives crew assignment windows; rotation and calendar views are available. |
| OPS-003 Dispatch Readiness Gate | Partial overall | Tug and crew checks are increasingly authoritative; inventory remains a manual audited confirmation and maintenance remains a manual tug state. |
| DOC-003 Controlled request workflow | Implemented | Credential renewal and recruitment controls reuse Document Control workflow. |
| DOC-005 Expiry and renewal | Partial overall | Crew credential expiry/renewal is implemented; vessel, insurance, permit, and corporate expiry coverage remains missing. |
| HSE-007 Training records | Partial | Credential/compliance readiness and training unavailability exist; full training plans, attendance, and expiry are deferred to Slice 13. |

## 6. Acceptance and Verification Evidence

The three newly added addons are included in the shared Docker install/upgrade command, so a colleague using the repository bootstrap receives the same module structure:

- `sedar_crew_compliance`
- `sedar_crewing_availability`
- `sedar_crew_scheduling`

The affected Odoo 19 regression run completed with 28 post-install tests and no failures or errors across dispatch, finance, recruitment operations, recruitment-to-crewing, credential compliance, availability, and scheduling. Focused tests cover:

- unverified credentials blocking assignment eligibility;
- controlled renewal evidence restoring verified credential status;
- medical classification and renewal visibility;
- dated unavailability blocking only overlapping assignments;
- temporary relief creating a concrete assignment and resolving the linked shortage;
- confirmation rejection for blocked crew assignments;
- replacement suggestions excluding unavailable or conflicting crew; and
- rejection of overlapping planned or active crew rotations.

Residual verification risk remains around complete manual role walkthroughs for the new Crewing menus and a brand-new database bootstrap. Automated module installation, upgrades, and affected workflow tests have passed, but the final pitch script should still be walked through from each intended user role.

## 7. Corrections to the Existing Status Report

The earlier sections of `docs/implementation-status.md` contain stale statements that predate Slices 7-9. This realignment supersedes those statements as follows:

| Earlier statement | Correct current position |
| --- | --- |
| Crew rotation is partial and has no planning interface. | Rotation periods, watches, relief crew, handover, state, calendar/list views, and overlap validation now exist. |
| Certificate renewal and controlled attachments are missing. | Controlled evidence requests, renewal state, verification, expiry exceptions, and readiness impact now exist. |
| Leave is only a generic availability example. | Approved Odoo Time Off now synchronizes to dated Crew Unavailability. |
| The highest next gaps are Slices 7-9. | Slices 7-9 are implemented; Technical Maintenance is the next dependency. |
| The old manpower demo resolves a shortage when opening a vacancy. | Slice 5 and ADR-0003 now preserve the operational shortage until a concrete operational resolution occurs. |

## 8. Remaining Cross-Module Risks

1. Tugboat technical availability is not yet owned by Maintenance. A manually available tug can pass readiness without a governed defect/work-order source.
2. Inventory readiness is still an audited manual confirmation. Stock quantities, fuel, lubricants, and spare parts are not yet authoritative.
3. Crew compliance is adequate for a demonstration but lacks several production maritime and medical details.
4. The scheduling views expose blockers but do not yet provide a consolidated forward fleet-and-crew readiness dashboard.
5. HSSE, Procurement, broader Finance, Attendance, Appraisal, Payroll inputs, corporate records, and executive KPIs remain outside the implemented Slices 1-9.
6. Generic demonstration policies must be replaced with SEDAR-approved rules during discovery; current behavior must not be described as statutory or production compliance.

## 9. Recommended Next Slice

Proceed with Slice 10: Technical Maintenance Foundation.

This is the correct next dependency because Service Order readiness already checks a tugboat's availability, but no authoritative maintenance workflow currently produces that fact. Slice 10 should introduce equipment history, planned maintenance, defects, work orders, maintenance holds, verified technical release, and representative dry-dock milestones. It must preserve ADR-0002 by feeding the automated Dispatch Readiness Gate rather than adding a separate human dispatch approval.

The Slice 10 implementation should use clearly labeled generic tugboat-company assumptions for maintenance intervals, criticality, equipment hierarchy, dry-dock milestones, and release authority until SEDAR confirms its actual policy. Spare-part reservation should remain visibly pending until Slice 11, which will add Inventory as the authoritative stock source.

## 10. Overall Alignment Decision

**Aligned, with documented demonstration limitations.**

Slices 1-9 solve the intended HR, recruitment, crewing, and Service Order staffing problems without breaking the accepted architecture. The project should not reopen those slices before Slice 10 unless a regression is found. The remaining details identified above should be carried as discovery or later-slice work rather than allowed to blur the next dependency.

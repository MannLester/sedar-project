# SEDAR Demonstration Implementation Status

| Item | Value |
| --- | --- |
| Assessment date | 2026-08-05 |
| Branch assessed | `sedar-new` |
| Baseline commit | `f7c3952` before Slice 5 working-tree changes |
| Active implementation | `sedar-new/` Odoo 19 Docker stack |
| Requirements source | `docs/project-requirements.md` |

## 1. Purpose

This document records what the SEDAR demonstration currently implements and what remains to be demonstrated. It is a repository evidence assessment, not a claim of production readiness.

## 2. Status Definitions

| Status | Meaning |
| --- | --- |
| Implemented | A working Odoo model, workflow, UI, portal route, or standard Odoo handoff exists and has been installed or upgraded in the shared stack. |
| Partial | A useful foundation or subset exists, but one or more requested capabilities or integrations are absent. |
| Not implemented | No demonstrable workflow exists in the active Odoo 19 custom addons or shared installation. |
| Future integration | The requirement depends primarily on an external product, device, or later production integration. |

## 3. Current Demonstration Architecture

The shared Docker setup installs these SEDAR addons and their Odoo dependencies:

| Area | Addons |
| --- | --- |
| Document Control | `sedar_document_control` |
| Marine Operations | `sedar_marine_operations`, `sedar_marine_dispatch` |
| Marine Finance | `sedar_marine_finance` plus standard Odoo `account` |
| Manpower and Careers | `sedar_manpower_planning`, `sedar_careers` |
| Recruitment | `sedar_applicant_intake`, `sedar_applicant_portal`, `sedar_recruitment_operations` |
| UI | `sedar_theme`, `sedar_ui_cards` |
| Fictional data | `sedar_service_order_demo`, `sedar_marine_dispatch_demo`, `sedar_manpower_planning_demo` |
| Repeatable recruitment fixtures | `sedar_recruitment_demo` |

### 3.1 Coverage at a glance

| Business area | Overall status | Summary |
| --- | --- | --- |
| Platform and shared data | Implemented | Odoo 19, PostgreSQL, Docker bootstrap, roles, portals, and shared records are working. |
| Tug Operations | Partial | Core Service Order, readiness, dispatch, execution, completion, and billing handoff work; fuel and AIS/GPS do not. |
| Marine Finance | Partial | Client Tariffs, Billing Review, customer invoicing, and payment foundation work; broader Finance remains incomplete. |
| Crewing and manpower | Partial | Crew profiles, manning, certificates, shortages, and hiring demand work; rotation, leave integration, and payroll do not. |
| HR and recruitment | Partial | The recruitment lifecycle through employee conversion works; attendance, appraisals, payroll, and broader self-service do not. |
| Document Control | Partial | Generic controlled forms and six recruitment forms work; broader corporate and vessel catalogues remain unseeded. |
| Technical Maintenance | Not implemented | Only a tugboat maintenance availability state exists; no PMS, defects, work orders, dry dock, or equipment history. |
| HSSE | Not implemented | Safety metadata exists in operations, but no formal HSSE module or workflow exists. |
| Procurement | Not implemented | No Purchase Request, approval, Purchase Order, supplier, receipt, or supplier-bill demonstration exists. |
| Inventory | Partial | A manual readiness confirmation exists; no stock, warehouse, spare-part, fuel, lubricant, or barcode workflow exists. |
| Marketing and CRM | Partial | Client, contact, vessel, tariff, Service Order, and portal records work; CRM opportunities and campaigns do not. |
| Executive Management | Partial | Operational and Finance queues exist; no consolidated KPI, profitability, audit, legal, or corporate-governance dashboard exists. |
| External integrations | Future integration | Power BI, Microsoft 365, DocuSign, and AIS/GPS are not connected. |

## 4. Implemented End-to-End Demonstrations

### 4.1 Client Service Order to Finance

```text
Client / Customer Relations
        -> Service Order
        -> Client Tariff and Confirmed Rate
        -> Tug and crew plan
        -> Dispatch Readiness Gate
        -> Marine Operation
        -> Tug Master actual time and Tug Completion
        -> Service Completion
        -> Billing Review
        -> Draft Odoo invoice
        -> Standard posting and payment
```

Demonstrable behavior includes client-specific tariffs, normalized service and location data, tug and crew assignments, certificate readiness, manual audited inventory confirmation, automatic operation creation, multi-tug completion, actual tug-hour billing, Billing Adjustments, draft invoicing, and standard Odoo payment status.

### 4.2 Crew Shortage to Employee

```text
Crew shortage
        -> Root-cause review
        -> Manpower request and approval
        -> Vacancy
        -> Careers publication
        -> ADM-3 application and attachments
        -> Applicant portal
        -> HR review and stage history
        -> Interview and ADM-4 appraisal
        -> accepted offer
        -> ADM-5 requirements
        -> Odoo employee conversion and HR onboarding source links
```

The shortage workflow distinguishes genuine permanent headcount demand from medical, certificate, leave, and temporary replacement issues.

### 4.3 Controlled Form Processing

The Document Control addon provides a document catalogue, controlled source files, typed template fields, generated requests, required-field validation, attachments, signatures, submission, review, approval, rejection, due dates, and assigned responsibility.

Approved source forms currently represented include:

- ADM-2
- ADM-3 Applicant and Employee Data Record
- ADM-4 Interview Appraisal Form
- CM-053 Company Interview Orientation Form
- ADM-4A Background Inquiry Form
- ADM-5 Employment Requirement List

## 5. Requirement Coverage by Department

### 5.1 Finance and Accounting

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| General Ledger | Partial | Standard Odoo Accounting is installed and owns entries created by posted customer invoices. | Configure and demonstrate representative journals, chart-of-accounts reporting, and traceable sample entries. |
| Accounts Receivable | Implemented | Completed services can create linked draft customer invoices; standard Odoo owns posting and payment. | Stabilize the clean seeded billing scenario and document the demo script. |
| Accounts Payable | Not implemented | No SEDAR supplier-bill or disbursement scenario exists. | Add a sample supplier bill and payment, preferably from Procurement. |
| Budgeting | Not implemented | No budget model, view, or fixture is installed. | Add a representative department or vessel budget and variance view. |
| Cash Flow | Not implemented | Payment status exists, but no cash-flow dashboard or forecast exists. | Add a basic cash-position and inflow/outflow demonstration. |
| Fixed Assets | Not implemented | Tugboats exist operationally but are not demonstrated as accounting assets. | Configure sample assets and depreciation. |
| Payroll | Not implemented | Employee conversion exists, but payroll is not installed or integrated. | Add demo payroll inputs and accounting handoff after rule discovery. |
| Bank Reconciliation | Not implemented | Standard accounting foundation exists, but no configured reconciliation scenario is included. | Add a sample bank statement and payment match. |
| Client Tariffs | Implemented | Effective-dated, terminal-specific approval and immutable revision controls exist. | Replace fictional rates after SEDAR approval. |
| Towage Billing | Implemented | Actual service quantity, minimum charge, adjustments, Billing Review, and draft invoice handoff exist. | Confirm final commercial rules and Philippine accounting configuration for production. |

### 5.2 Tug Operations

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Service Order intake | Implemented | Internal dashboard and client portal creation use normalized service, vessel, location, schedule, and tug fields. | Refine demo data and role-specific walkthrough. |
| Client dashboard | Implemented | Portal users can create and view only their commercial account's Service Orders. | Expand client notifications and documents if needed. |
| Tug assignment and planning | Implemented | Tug assignments, tug classes, bollard pull, manning templates, and requested timing are modeled. | A calendar or timeline scheduling UI would improve demonstration clarity. |
| Automated readiness | Implemented | Tugboat, crew, certificate, and manual inventory readiness determine whether an order is Ready. | Replace manual inventory confirmation with Inventory truth. |
| Dispatch and Marine Operation | Implemented | Ready orders create one execution record with tug and crew manifests. | Add richer operator walkthrough and notifications if required. |
| Voyage or operation logs | Partial | Movement milestones, activity logs, delays, actual times, notes, and evidence exist. | Add a dedicated voyage-log presentation and any statutory log fields confirmed by SEDAR. |
| Tug Completion | Implemented | Assigned Tug Masters record actual time and completion; all active tugs are required. | Confirm operational evidence and correction policy with SEDAR. |
| Fuel monitoring | Not implemented | Tugboat fuel capacity exists, but no fuel transaction or consumption workflow exists. | Add fuel receipts, issues, sounding/remaining balance, and operation consumption. |
| Towage billing | Implemented | Marine facts hand off automatically to Finance Billing Review. | Confirm tariff formulas and exception rules. |
| AIS/GPS tracking | Future integration | No live or mock position feed is installed. | Add a provider adapter or clearly labeled mock tracking dashboard. |

### 5.3 Technical and Maintenance

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Tug availability | Partial | Tugboats have availability states, including maintenance hold, which affect readiness. | Make Maintenance the authoritative source of availability. |
| Planned Maintenance System | Not implemented | No maintenance plan or interval model is installed. | Add standard Odoo Maintenance or a marine PMS extension. |
| Defect reporting | Not implemented | No defect workflow exists. | Add defect classification, severity, assignment, and closure. |
| Work orders | Not implemented | No technical work-order workflow exists. | Add planned and corrective work orders. |
| Dry-dock planning | Not implemented | No dry-dock records or milestones exist. | Add a representative dry-dock plan. |
| Spare parts consumption | Not implemented | No Inventory or work-order parts issue exists. | Connect work orders to stock reservations and consumption. |
| Equipment history | Not implemented | Tugboat master data exists, but onboard equipment history does not. | Add equipment hierarchy, maintenance, replacement, and defect history. |

### 5.4 HSSE

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Service safety metadata | Partial | Service Orders include safety and permit-related planning information; completion evidence and delays can be recorded. | Formalize HSSE ownership and exception behavior. |
| Incident reporting | Not implemented | No incident model or workflow exists. | Add incident classification, investigation, evidence, actions, and closure. |
| Near-miss reporting | Not implemented | No near-miss workflow exists. | Add a near-miss type using the shared incident foundation. |
| Inspections | Not implemented | No inspection checklist or findings model exists. | Add vessel and workplace inspection examples. |
| Permits | Partial | Documents can be catalogued and Service Orders can carry permit requirements, but there is no permit register with validity. | Add permit records, expiry, owner, and operational impact. |
| Risk assessments | Not implemented | No risk matrix or assessment workflow exists. | Add hazards, controls, likelihood, impact, residual risk, and approval. |
| Compliance audits | Not implemented | No audit and corrective-action workflow exists. | Add a representative audit and overdue finding. |
| Safety meetings | Not implemented | No meeting, attendance, topic, or action workflow exists. | Add a sample toolbox or safety meeting. |
| Training records | Partial | Crew certificates and expiry exist, but general HSSE training plans and attendance do not. | Add training requirements, sessions, attendance, and expiry. |

### 5.5 Crewing

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Crew profiles | Implemented | Employee-linked crew profiles include rank, identifiers, availability, and home tugboat. | Add production-approved personnel and privacy rules later. |
| Manning templates | Implemented | Services define required ranks, counts, and certificates. | Confirm requirements per actual tug class and operation. |
| Crew assignment | Implemented | Tug plans compare assigned crew with requirements and create shortages. | Add a broader rotation calendar. |
| Crew rotation | Partial | Assignment and availability exist, but no rotation-cycle planning interface exists. | Add rotation periods, relief planning, and handover. |
| STCW and certificates | Implemented | Certificate types, numbers, issue/expiry dates, and readiness checks exist. | Add controlled document attachments and renewal workflow. |
| Medicals | Implemented | Medical certificate expiry can block readiness and create a non-hiring action. | Add provider, examination details, and renewal scheduling if required. |
| Leave | Partial | Availability can represent leave and demonstrate a temporary shortage. | Integrate standard Odoo Leave requests, approval, and dates. |
| Payroll integration | Not implemented | Crew assignments do not produce payroll inputs. | Define eligible service, overtime, allowance, and payroll rules. |
| Shortage root-cause review | Implemented | Headcount, medical, certificate, leave, and temporary outcomes are separated. | Confirm review authority and service-level targets. |

### 5.6 Procurement

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Purchase Requests | Not implemented | No request model or approval workflow is installed. | Add department requests linked to maintenance or stock need. |
| Purchase Orders | Not implemented | Odoo Purchase is not part of the shared custom-module bootstrap. | Install and configure standard Purchase with a sample order. |
| Supplier management | Not implemented | Shared partner records exist, but no supplier qualification or procurement view is demonstrated. | Add suppliers, terms, documents, and performance. |
| Approval workflow | Not implemented | Manpower approvals exist but are not reusable procurement approvals. | Add amount- or category-based Purchase Request approval. |
| Finance and receipt linkage | Not implemented | No request-to-order-to-receipt-to-bill chain exists. | Demonstrate the standard Odoo handoffs. |

### 5.7 Inventory

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Inventory readiness | Partial | Operations records an audited manual readiness confirmation. | Replace it with authoritative stock availability. |
| Spare parts | Not implemented | No product and stock workflow is installed for spare parts. | Add parts catalogue, quantities, locations, and reorder rules. |
| Fuel and lubricants | Not implemented | Fuel capacity exists only as tugboat master data. | Add products, tanks/locations, receipts, issues, and consumption. |
| Office supplies | Not implemented | No supply stock records exist. | Add representative consumable products and transactions. |
| Warehouse management | Not implemented | No warehouse, vessel location, receipt, issue, or transfer demo exists. | Install and configure standard Odoo Inventory. |
| Barcode support | Not implemented | No Barcode application or scan scenario is installed. | Add a representative barcode receipt or issue. |

### 5.8 Human Resources and Recruitment

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Employee records | Implemented | Standard Odoo employees are seeded and successful applicants can convert to employees. | Expand onboarding and production HR fields after discovery. |
| Recruitment demand | Implemented | Approved manpower requests produce traceable vacancies. | Confirm approval roles and staffing policies. |
| Careers publication | Implemented | Approved vacancies have publication metadata and a public endpoint for the website. | Stabilize the seeded published vacancy on reused databases. |
| ADM-3 application | Implemented | Public intake creates Odoo applicants, structured profile, education, employment, and documents. | Add more validation only after SEDAR confirms rules. |
| Applicant dashboard | Implemented | Secure activation, owned applications, public status, timeline, and document download exist. | Add notification delivery if required. |
| HR processing dashboard | Implemented | Recruiter, deadlines, next actions, overdue search, controlled stages, and history exist. | Add reporting totals and demo fixture applicants. |
| Interview scheduling | Implemented | Interviews synchronize Calendar, support confirmation/reschedule, and generate ADM-4. | Add email/calendar provider integration later. |
| Employment requirements | Implemented | ADM-5 typed values and attachments can be submitted and approved. | Add production document validation and expiry rules. |
| Employee dashboard | Partial | Converted employees have a portal foundation showing linked application and onboarding documents. | Add employee self-service features and role transition policy. |
| Attendance | Not implemented | No attendance application or seeded records are part of the stack. | Install/configure standard Attendance and a sample summary. |
| Performance evaluation | Not implemented | No appraisal workflow exists for employees; ADM-4 is applicant interview appraisal only. | Install/configure employee Appraisals or a demo equivalent. |
| Payroll | Not implemented | No payroll module or rules are installed. | Add only after Philippine payroll discovery and validation. |

### 5.9 Document Control

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Catalogue and controlled source | Implemented | Document types and source files include code, title, department, category, version, state, and confidentiality. | Add broader departmental examples. |
| Typed fillable forms | Implemented | Text, date, integer, decimal, boolean, selection, attachment, and signature values are supported. | Add field-level help and validation where approved. |
| Request workflow | Implemented | Draft, in-progress, submitted, reviewed, approved, and rejected processing exists. | Add reminders and escalation if needed. |
| Recruitment forms | Implemented | Six approved applicant and employee forms are represented. | Continue the extract, approve, catalogue, implement workflow for new forms. |
| Contracts | Not implemented | The generic catalogue can hold them, but no representative contract type or lifecycle is seeded. | Add contract metadata, party, dates, approval, and renewal example. |
| Vessel certificates | Not implemented | Crew certificates exist separately, but controlled vessel certificate examples are absent. | Add vessel ownership, validity, expiry, and renewal. |
| Insurance | Not implemented | No insurance policy type or sample record exists. | Add policy, insurer, coverage, validity, and renewal. |
| Permits | Partial | Generic documents and Service Order permit requirements exist. | Add a permit register and expiry dashboard. |
| Board resolutions | Not implemented | No representative board-resolution catalogue or workflow exists. | Add resolution number, date, subject, approval, and attachment. |
| ISO documents | Not implemented | No ISO manual, procedure, revision, distribution, or acknowledgement example exists. | Add representative controlled ISO documents. |
| Expiry dashboard | Not implemented | Individual certificate expiry is checked in Crewing, but Document Control has no unified expiry view. | Add cross-document expiry and renewal status. |

### 5.10 Marketing and Customer Management

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Client master data | Implemented | Odoo partners, contacts, assisted vessels, service history, and Client Tariffs are linked. | Add richer account segmentation if needed. |
| Customer Relations intake | Implemented | Internal Service Order dashboard supports client-facing order placement. | Add assigned officer and communication activity if required. |
| Client portal | Implemented | Clients see only their account's Service Orders and authorized activity. | Add quotations and documents if included in the pitch. |
| CRM opportunities and campaigns | Not implemented | Standard CRM is not configured in the shared demonstration. | Add one opportunity-to-Service-Order example. |

### 5.11 Corporate and Executive Management

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Operational dashboard | Implemented | Service Order dashboard and role-focused queues expose operational states and blockers. | Add consolidated executive presentation. |
| Financial dashboard | Partial | Billing Review, Pricing Exception, invoices, and payment states are visible. | Add financial KPI summaries and standard reports. |
| Fleet utilization | Partial | Tug assignments, operation timing, and availability exist as source data. | Add approved utilization formulas and KPI cards. |
| Vessel availability | Partial | Tugboat availability and readiness blockers exist. | Add trend and reason summaries sourced from Maintenance. |
| Profitability | Not implemented | Revenue can be calculated, but attributable operating costs are absent. | Add fuel, labor, parts, and other approved cost sources. |
| HSSE KPIs | Not implemented | No incident, inspection, risk, or audit models exist. | Build after HSSE workflows. |
| Executive KPI dashboard | Not implemented | No cross-functional management dashboard exists. | Add drill-down KPIs using governed source records. |
| Board resolutions | Not implemented | No corporate-resolution workflow exists. | Add representative controlled records. |
| Legal cases | Not implemented | No legal-case model exists. | Add case, counsel, dates, exposure, documents, and actions. |
| Insurance | Not implemented | No policy register exists. | Add corporate and vessel insurance examples. |
| Internal Audit | Not implemented | No audit-plan or findings workflow exists. | Add a sample audit and corrective actions. |

### 5.12 External Programs and Integrations

| Requirement | Status | Current evidence | Remaining demonstration work |
| --- | --- | --- | --- |
| Power BI | Future integration | Odoo records provide potential source data, but no dataset or report exists. | Define governed datasets and create a mock or live executive report. |
| Microsoft 365 | Future integration | No Outlook, Teams, or SharePoint integration exists. | Select specific use cases and configure approved connectors. |
| DocuSign | Future integration | Odoo stores signatures and attachments, but no envelope integration exists. | Add mock or live contract signing status. |
| AIS/GPS | Future integration | No location provider or map exists. | Select provider, data contract, update interval, and retention policy. |

## 6. Current Demo Data and Verification Notes

The Docker stack has been verified to load the combined custom modules on Odoo 19. The local demonstration database has included representative service orders, tugboats, crew profiles, employees, manpower records, vacancies, and Marine Operations. Exact record counts can vary on a reused database because Odoo post-install hooks do not automatically overwrite existing fictional fixtures during module upgrades.

Slice 1 adds `sedar_recruitment_demo`, a dedicated non-production fixture addon that reconciles
named applicant, interview, ADM-5, applicant-portal, employee-conversion, and recruitment-user
scenarios during module install and upgrade. This narrows the earlier repeatability gap for the
HR and job-application demonstration baseline. The older manpower demo still marks the permanent
headcount shortage resolved when the vacancy opens; the slice roadmap records that semantic
discrepancy for a later ADR-backed workflow correction.

Slice 2 extends `sedar_recruitment_operations` with an HR-facing Recruitment Dashboard. The
dashboard uses source-record actions rather than copied totals: pipeline graph/pivot views open
`hr.applicant`, interview queues open `sedar.applicant.interview`, ADM-5 queues open
`sedar.document.request`, and open-vacancy queues open `sedar.job.vacancy`.

Slice 3 adds generic tugboat-company pre-employment controls for marine crew applicants. After
ADM-4 interview completion, HR can generate internal ADM-4A Background Inquiry and CM-053 Company
Interview Orientation requests from the approved Document Control catalogue. The applicant portal
sees only a general progress message; confidential background/orientation content stays in HR-only
document requests. ADM-5 employment requirements are blocked until both controls are approved.

Slice 4 adds `sedar.applicant.offer` for explicit hiring decisions and applicant offer response.
After background/orientation controls are approved, HR issues an offer from the applicant record or
Hiring Decisions and Offers menu. The applicant portal can accept or decline an issued offer. ADM-5
employment requirements and employee conversion are now gated by an accepted offer, so the demo no
longer treats document submission alone as the hiring decision.

Slice 5 adds traceable Applicant-to-Employee Onboarding. Employee conversion remains based on Odoo
Recruitment's native employee creation, but SEDAR now writes source links from employee to applicant,
vacancy, accepted offer, and approved ADM-5 request. The conversion action is idempotent and updates
vacancy/manpower fulfillment exactly once from linked employee records. ADR-0003 separates HR
headcount fulfillment from operational shortage resolution: opening a vacancy and hiring an employee
do not automatically mark the original Service Order crew shortage resolved.

A Slice 2-5 control-hardening pass now closes the realignment gaps found before Slice 6. Assigned
interviewers see only assigned interviews and appraisal records. Confidential recruitment document
requests and values are no longer broadly visible to every internal user. HR Recruitment Manager
authority is enforced server-side for background/orientation approval, offer decisions, internal offer
acceptance, employee conversion, and onboarding control. Offer acceptance records actor and source,
and employee conversion assigns an onboarding owner, checklist, activity, and portal-to-employee
identity link.

Slice 6 adds the first Marine Crew Onboarding handoff. Marine hires now receive a crewing-owned
`sedar.crew.onboarding` case after employee conversion. The case creates or links a Crew Profile,
inherits required credential and medical types from the manpower request or manning templates,
tracks blockers, and marks the profile deployment eligible only after Crewing assigns the home
tugboat and valid required credentials exist. Non-marine hires stop at the HR employee record.
Deployment eligibility still does not resolve the original Service Order shortage until Operations
or Crewing assigns a qualified profile to a concrete requirement.

The repository contains automated tests for the marine readiness/completion lifecycle and Marine Finance calculations and controls. Applicant portal and recruitment slices have been manually verified through Odoo module upgrades and representative portal/backend workflows.

## 7. Demonstration Gaps That Affect Existing Flows

These are the highest-value missing capabilities because they already connect to implemented records:

1. Crew certificate and medical records should link to controlled document evidence and renewal actions.
2. Leave, training, and temporary relief should provide dated crew availability facts.
3. Crew rotation and Service Order scheduling should consume deployment-eligible crew facts.
4. Maintenance should become the source of tugboat technical availability.
5. Inventory should replace manual Inventory Readiness Confirmation and supply fuel and spare-part facts.
6. Procurement should replenish maintenance and inventory shortages.
7. Executive KPIs should use the operational, HR, and financial source records already available.

## 8. Recommended Next Demonstration Slices

### Slice 6: Marine Crew Onboarding

Create the explicit handoff from successful HR hire to marine Crew Profile, rank, home tugboat,
credential requirements, and deployment-eligibility state. This is the next dependency because a
standard Odoo employee is not automatically usable as crew.

### Slice 7: Crew Credentials and Medical Renewal

Connect credential and medical validity to controlled evidence, expiry visibility, and readiness.

### Slice 8: Leave, Training, and Temporary Relief

Add dated unavailability and relief workflows so not every crew shortage becomes hiring demand.

### Slice 9: Crew Rotation and Service Order Scheduling

Build the planning layer that assigns deployment-eligible crew to tugboats and Service Orders without overlaps.

### Slice 10 onward

Proceed with Technical Maintenance, Inventory/Fuel, Procurement, HSSE, broader ERP demonstrations,
and the final executive dashboard in the order defined by `sedar-planning/implementation-slice-roadmap.md`.

## 9. Production Readiness Disclaimer

The implemented capabilities demonstrate architecture, data relationships, workflows, controls, and user experience. They are not yet approved for live SEDAR operations. Production use requires stakeholder discovery, real-data validation, security hardening, access review, statutory and accounting validation, migration planning, integration testing, backup and recovery design, performance testing, training, and formal acceptance.

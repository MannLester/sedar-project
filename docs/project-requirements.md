# SEDAR Integrated ERP and Marine Fleet Management System

## Project Requirements Document

| Item | Value |
| --- | --- |
| Organization | SEDAR Tug Services, Inc. |
| Solution | Integrated ERP and Marine Fleet Management System |
| Core platform | Odoo 19 |
| Document status | Demonstration baseline |
| Version | 1.0 |
| Date | 2026-08-05 |
| Primary audience | SEDAR leadership, department representatives, project team, and developers |

## 1. Purpose

This document defines the business and demonstration requirements for a centralized SEDAR ERP and Marine Fleet Management System. It converts the President's digital-transformation vision into a structured target that can guide demonstrations, planning, validation, and later discovery with SEDAR stakeholders.

The current project is a demonstration, not a production deployment. Each required business area must be visible, organized, and understandable enough to show the intended end-to-end system. Production configuration, statutory validation, final approval limits, real tariffs, live integrations, migration, and operational rollout remain subject to formal discovery and acceptance after project approval.

## 2. Business Context

SEDAR currently seeks to replace disconnected systems, department-specific spreadsheets, duplicate encoding, and manual handoffs with one shared platform. The target system must connect commercial demand, tug operations, vessels, crew, maintenance, safety, procurement, inventory, human resources, finance, controlled documents, and management reporting.

The system must provide a single source of truth in which authorized users enter information once and downstream processes consume the same record. The demonstration must show how operational events can produce staffing, compliance, document, and financial consequences without recreating the same information in separate files.

## 3. Vision

SEDAR will operate as a modern, data-driven tug service provider with integrated operational control, financial transparency, regulatory visibility, reliable records, accountable approvals, and timely management information.

The solution should support:

- sustainable growth and additional tugboats, clients, personnel, and locations;
- safe and reliable marine operations;
- stronger corporate governance and internal controls;
- improved asset utilization and service profitability;
- better client communication and service visibility;
- timely compliance and document-expiry monitoring; and
- executive decisions based on consistent operational and financial data.

## 4. Project Objectives

The demonstration shall:

1. Present Odoo 19 as the central ERP and workflow platform.
2. Show a connected lifecycle from client Service Order through planning, execution, Service Completion, Billing Review, invoice, and payment.
3. Show how tug and crew readiness affect dispatch and how genuine crew demand can create a vacancy and recruitment process.
4. Provide controlled, typed, and reviewable business documents rather than disconnected form files.
5. Organize every requested department and capability in a coherent navigation and data model, even when a capability is represented only by a demonstration workflow.
6. Keep operational, HR, safety, and financial authority separated through roles, workflow states, and audit fields.
7. Identify which capabilities can use standard Odoo modules, which require SEDAR customization, and which require external integration.

## 5. Scope Principles

### 5.1 Demonstration scope

- Fictional clients, employees, tugboats, rates, certificates, transactions, and scenarios may be used.
- A representative happy path and selected exception paths are sufficient for each business area.
- Complex formulas may be entered manually when SEDAR has not yet provided an approved rule.
- External systems may be represented by a visible integration status, sample import, or mock data feed.
- Dashboards may use seeded values but must identify their source records.
- Standard Odoo workflows should be reused when they meet the requirement.

### 5.2 Production scope excluded from this baseline

- Real SEDAR data migration and reconciliation
- Final Philippine tax, payroll, labor, maritime, and electronic-invoicing validation
- Production cybersecurity certification, penetration testing, disaster recovery, and high availability
- Final approval matrices, segregation-of-duties signoff, and record-retention schedules
- Live bank, AIS/GPS, Microsoft 365, Power BI, DocuSign, biometric, barcode-device, or government integrations
- Production infrastructure sizing, support service levels, and rollout planning
- Exact automated surcharge, rebate, overtime, fuel, and consumable formulas not yet confirmed by SEDAR

## 6. Stakeholders and User Roles

| Role | Demonstration responsibility |
| --- | --- |
| President / Board | Reviews strategic KPIs, financial transparency, governance, and exceptions. |
| Executive Management | Reviews utilization, availability, profitability, compliance, and departmental performance. |
| Customer Relations / Marketing | Manages clients, contacts, requests, quotations, tariffs, and service communication. |
| Client | Places and tracks Service Orders and sees authorized operational updates. |
| Operations User | Plans tug assignments, crew, schedule, readiness, and service execution. |
| Tug Master | Records actual start, Tug Completion, completion notes, and evidence for an assigned tugboat. |
| Technical / Maintenance User | Plans maintenance, records defects and work orders, and manages equipment history. |
| Crewing User | Manages ranks, assignments, rotations, certificates, medicals, leave, and shortages. |
| HSSE User | Records incidents, near misses, inspections, permits, risk assessments, audits, and training. |
| HR User | Manages applicants, interviews, requirements, employees, attendance, evaluation, and recruitment. |
| Procurement User | Manages purchase requests, approvals, suppliers, and purchase orders. |
| Inventory User | Manages warehouses, spare parts, fuel, lubricants, consumables, and barcode transactions. |
| Billing Officer | Reviews completed services, quantities, adjustments, and draft invoices. |
| Accounting Manager | Approves Client Tariffs and controls standard Odoo accounting records. |
| Document Controller | Maintains controlled templates, versions, owners, approvals, and expiry records. |
| System Administrator | Configures users, access, master data, integrations, and demonstration fixtures. |

## 7. Target Solution Architecture

### 7.1 Core platform

Odoo 19 shall serve as the primary transactional system and single source of truth. Standard Odoo applications should own established ERP behavior such as accounting entries, invoices, payments, employees, recruitment, purchasing, inventory movements, and maintenance orders. SEDAR custom modules should own marine-specific terminology, relationships, readiness rules, and cross-department handoffs.

### 7.2 Proposed components

| Component | Responsibility |
| --- | --- |
| Odoo 19 | Core records, workflow, role access, portal, accounting, HR, procurement, inventory, maintenance, and documents. |
| SEDAR custom addons | Service Orders, tug and crew readiness, Marine Operations, marine billing handoff, controlled SEDAR forms, and domain dashboards. |
| PostgreSQL | Odoo transactional database. |
| Power BI | Future executive analytics and board-level reporting. |
| Microsoft 365 | Future email, Teams, SharePoint, and collaborative document integration. |
| DocuSign | Future external electronic signature and contract execution. |
| AIS/GPS provider | Future live tugboat position and movement feed. |
| Dedicated maritime system | Optional future extension if maintenance, crewing, or fleet complexity exceeds the practical custom Odoo scope. |

### 7.3 Architectural boundaries

- A Service Order is one billable tug assist or move at one Terminal.
- A Marine Operation is the execution record created for a Ready Service Order.
- Service Completion occurs only when every active tug assignment has a submitted Tug Completion.
- SEDAR modules own marine execution and Billing Review; standard Odoo Accounting owns invoices, receivables, ledger entries, payments, reconciliation, and credit notes.
- Inventory readiness may be manually confirmed for the demonstration, but a future Inventory module must become the authoritative source.

### 7.4 Platform decision context

The source requirement considered four principal platform approaches:

| Platform | Relevant strengths | SEDAR consideration |
| --- | --- | --- |
| Microsoft Dynamics 365 Business Central | Strong accounting, purchasing, inventory, Microsoft ecosystem, and Power BI integration | Suitable for a medium-sized organization but requires substantial marine customization and generally higher implementation cost. |
| Odoo | Integrated accounting, purchase, inventory, HR, recruitment, maintenance, fleet, portal, documents, and mobile foundations | Recommended core platform because it is modular, customizable, scalable for the demonstration, and provides a practical capability-to-cost balance. |
| Star Information Systems / ShipNet | Shipping-oriented technical management, procurement, inventory, HSEQ, crewing, and finance | Strong maritime specialization; may be considered later if fleet complexity outgrows practical Odoo customization. |
| ABS NS5 | Mature maintenance, HSE, purchasing, crewing, and compliance capabilities | Strong specialized option for commercial marine operations; may be considered as a future dedicated fleet component. |

The demonstration uses Odoo 19 as the approved working assumption. This does not prevent a later integration with a dedicated maritime system when fleet scale, regulatory complexity, or maintenance depth justifies it.

## 8. End-to-End Business Flows

### 8.1 Client-to-payment flow

1. A client or Customer Relations Officer creates a Service Order.
2. The system identifies the client, assisted vessel, service, Terminal, requested schedule, tug requirement, and applicable Client Tariff.
3. Operations assigns tugboats and qualified crew.
4. The Dispatch Readiness Gate checks tugboat, crew, required certificates, and inventory readiness.
5. A Ready Service Order creates one Marine Operation.
6. Each Tug Master records actual service time and submits Tug Completion.
7. Service Completion sends the order to Finance Billing Review.
8. Finance reviews the Confirmed Rate, actual quantity, minimum charge, and Billing Adjustments.
9. Finance creates a draft Odoo customer invoice.
10. Standard Odoo Accounting posts the invoice and records payment.

### 8.2 Crew-shortage-to-employment flow

1. Service planning identifies a crew shortage.
2. Crewing reviews whether the cause is headcount, leave, certification, medical, or temporary availability.
3. A genuine headcount shortage creates a manpower request for approval.
4. An approved request creates an internal vacancy.
5. HR publishes the vacancy to Careers.
6. An applicant submits the ADM-3 pre-employment form and attachments.
7. HR reviews and qualifies, clarifies, or rejects the application.
8. HR schedules an interview and completes ADM-4 appraisal.
9. The applicant submits ADM-5 employment requirements.
10. HR verifies requirements and converts the successful applicant into an employee.
11. Future crewing onboarding assigns rank, certificates, readiness, and tugboat deployment eligibility.

### 8.3 Maintenance and inventory flow

1. A tugboat or equipment item reaches a planned interval or reports a defect.
2. Technical creates a work order and reserves required spare parts.
3. Procurement handles shortages through purchase requests and purchase orders.
4. Inventory receives and issues parts to the work order.
5. Maintenance completion updates equipment history and tugboat availability.
6. Tugboat availability immediately affects the Dispatch Readiness Gate.

### 8.4 HSSE and compliance flow

1. Operations or crew records an incident, near miss, inspection, or identified hazard.
2. HSSE assesses severity and risk, assigns corrective actions, and tracks due dates.
3. Related permits, evidence, meetings, audits, and training records are linked.
4. Open critical actions or expired requirements are visible to Operations and Management.

## 9. Functional Requirements

Priority uses `Must` for a required demonstration capability, `Should` for an important supporting capability, and `Future` for a visible integration or production extension.

### 9.1 Platform and master data

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| PLT-001 | The system shall use one Odoo database for shared departmental records. | Must | A record created in one workflow is visible to authorized downstream users without re-entry. |
| PLT-002 | The system shall maintain shared clients, contacts, employees, users, tugboats, vessels, ports, Terminals, services, suppliers, and products. | Must | Representative master records are available through normalized selections. |
| PLT-003 | The system shall apply role-based access and server-side workflow authorization. | Must | Demo users see and execute only role-appropriate actions. |
| PLT-004 | The system shall record workflow state, responsible user, dates, and important approval or completion metadata. | Must | Representative records show traceable actors and timestamps. |
| PLT-005 | The shared Docker setup shall install required custom addons and fictional demo data. | Must | A team member can start the documented Odoo 19 stack without manual module installation. |

### 9.2 Finance and Accounting

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| FIN-001 | Standard Odoo Accounting shall provide the General Ledger and journal-entry foundation. | Must | A posted service invoice produces standard accounting entries. |
| FIN-002 | The system shall support customer invoicing and Accounts Receivable from completed Service Orders. | Must | An eligible Billing Review creates one linked draft invoice that can be posted and paid. |
| FIN-003 | The system shall support supplier bills and Accounts Payable. | Should | A sample supplier bill and payment can be demonstrated using standard Odoo. |
| FIN-004 | The system shall support budgets and budget-versus-actual reporting. | Should | A sample department or vessel budget can be compared with actual transactions. |
| FIN-005 | The system shall support cash position and cash-flow visibility. | Should | A demonstration report shows sample inflows, outflows, and current cash position. |
| FIN-006 | The system shall maintain fixed assets and depreciation. | Should | A tugboat or equipment asset shows value, depreciation, and accounting history. |
| FIN-007 | Payroll results shall integrate with Finance without creating a separate ledger. | Future | A sample payroll result produces or links to standard accounting entries. |
| FIN-008 | The system shall support bank reconciliation through standard Odoo controls. | Future | A sample bank transaction can be matched to an invoice payment. |
| FIN-009 | Client Tariffs shall be client-, service-, Terminal-, date-, and optional tug-class-specific. | Must | Confirmation freezes the approved rate and preserves its source tariff. |
| FIN-010 | Billing shall use actual service quantities and explained adjustments. | Must | A completed multi-tug service shows actual tug-hours, minimum charge, and separate adjustments. |

### 9.3 Tug Operations

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| OPS-001 | Clients or authorized staff shall create and track Service Orders. | Must | A portal or internal user submits a normalized Service Order and sees its status. |
| OPS-002 | The system shall support tug scheduling and assignment. | Must | Operations assigns required tugboats and planned times to a Service Order. |
| OPS-003 | The system shall evaluate tugboat, crew, certificate, and inventory readiness. | Must | Representative ready and blocked orders show the reason for their result. |
| OPS-004 | A Ready Service Order shall create one Marine Operation. | Must | Passing readiness creates one awaiting-start execution record. |
| OPS-005 | The system shall record voyage or operation logs, tug movements, delays, actual times, and completion evidence. | Must | A Marine Operation displays its event history and participating tugboats and crew. |
| OPS-006 | Every participating Tug Master shall submit Tug Completion before Service Completion. | Must | A two-tug service stays incomplete until both declarations are submitted. |
| OPS-007 | The system shall monitor fuel usage by tugboat, operation, date, and transaction type. | Should | A sample operation shows opening, issued, consumed, and remaining fuel. |
| OPS-008 | Towage billing shall consume the completed operation and Confirmed Rate. | Must | Billing Review uses actual operational facts and creates a linked draft invoice. |
| OPS-009 | The system shall display AIS/GPS position and movement status when an external feed is available. | Future | A map or mock feed displays timestamped tugboat positions and integration status. |

### 9.4 Technical and Maintenance

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| MNT-001 | The system shall provide a Planned Maintenance System for tugboats and onboard equipment. | Must | A maintenance plan generates or schedules a work order by date or running interval. |
| MNT-002 | The system shall record defects, corrective work orders, priorities, responsibility, labor, parts, and completion. | Must | A defect progresses from report to verified closure. |
| MNT-003 | The system shall plan dry docking, milestones, expected costs, and required documents. | Should | A sample tugboat displays a dry-dock plan and milestone status. |
| MNT-004 | Maintenance work shall reserve and consume spare parts from Inventory. | Must | A work order shows requested, reserved, and consumed parts. |
| MNT-005 | The system shall preserve equipment installation, maintenance, defect, and replacement history. | Must | An equipment record shows chronological service history. |
| MNT-006 | Maintenance status shall affect tugboat operational availability. | Must | A tugboat on maintenance hold cannot pass the Dispatch Readiness Gate. |

### 9.5 HSSE

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| HSE-001 | The system shall record incidents and near misses with classification, vessel, people, date, location, evidence, and status. | Must | A sample incident progresses through investigation and closure. |
| HSE-002 | The system shall manage inspections and findings. | Must | A checklist inspection creates corrective findings with owners and due dates. |
| HSE-003 | The system shall track permits, validity, responsible owner, and expiry. | Must | Expiring or missing permits appear as visible exceptions. |
| HSE-004 | The system shall record risk assessments, hazards, controls, likelihood, impact, and residual risk. | Must | A sample operation or task has a reviewable risk assessment. |
| HSE-005 | The system shall manage compliance audits and corrective actions. | Should | Audit findings are assigned and tracked to closure. |
| HSE-006 | The system shall record safety meetings, attendance, topics, and actions. | Should | A sample safety meeting links attendees and open actions. |
| HSE-007 | The system shall track safety and compliance training records and expiry. | Must | A crew profile shows required training and readiness impact. |

### 9.6 Crewing

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| CRW-001 | The system shall maintain crew profiles linked to employee records. | Must | A crew member has employee, rank, identification, readiness, and home-tug information. |
| CRW-002 | The system shall support crew scheduling, assignment, manning requirements, and rotation. | Must | A Service Order compares required positions with assigned qualified crew. |
| CRW-003 | The system shall track STCW and other certificate numbers, issue dates, expiry dates, and required types. | Must | Expired or missing certificates block readiness and appear in an exception scenario. |
| CRW-004 | The system shall track medical validity and readiness. | Must | An expired medical produces a visible compliance shortage rather than a headcount vacancy. |
| CRW-005 | The system shall track leave and temporary unavailability. | Must | An employee on leave creates a temporary staffing resolution path. |
| CRW-006 | Crewing assignments and payroll-relevant service facts shall be available to Payroll. | Future | A sample payroll input shows service or assignment source records without duplicate encoding. |
| CRW-007 | The system shall distinguish genuine headcount shortages from temporary or compliance shortages. | Must | Headcount, leave, medical, and certification examples produce different actions. |

### 9.7 Procurement

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| PRC-001 | Departments shall create Purchase Requests with justification, required date, items, quantities, and cost estimate. | Must | A maintenance or inventory need creates a traceable Purchase Request. |
| PRC-002 | Purchase Requests and Purchase Orders shall follow configurable approval states. | Must | A sample request requires approval before a Purchase Order is issued. |
| PRC-003 | Standard Odoo Purchase shall manage Purchase Orders and receipt linkage. Awarded request lines shall be grouped into one Purchase Order per winning Bidder. | Must | The approved A/B/C example produces one Purchase Order for Bidder 1 containing A and B, one for Bidder 3 containing C, and linked receipts. |
| PRC-004 | The system shall maintain supplier records, contacts, terms, qualifications, and performance indicators. | Should | A supplier profile shows commercial and evaluation information. |
| PRC-005 | Procurement, Inventory, and Finance shall share the same item, receipt, supplier, and bill references. | Must | A sample transaction can be followed from request to receipt and supplier bill. |

### 9.8 Inventory

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| INV-001 | The system shall maintain spare parts, fuel, lubricants, office supplies, units, categories, and reorder rules. | Must | Representative item records show stock by warehouse or location. |
| INV-002 | The system shall manage receipts, issues, transfers, returns, and adjustments. | Must | A sample item can be received and issued to a vessel, operation, or work order. |
| INV-003 | The system shall support warehouse and vessel stock locations. | Must | Stock quantities are visible by main warehouse and selected tugboat. |
| INV-004 | The system shall support barcode-assisted stock transactions. | Should | A sample barcode identifies an item and records a receipt or issue. |
| INV-005 | The authoritative inventory result shall feed the Dispatch Readiness Gate. | Must | Required stock availability automatically satisfies or blocks readiness. |
| INV-006 | Fuel and lubricant transactions shall be traceable to tugboat and operation. | Must | Consumption can be summarized by tugboat and Service Order. |

### 9.9 Human Resources and Recruitment

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| HR-001 | The system shall maintain employee records, departments, jobs, contacts, and employment status. | Must | A successful applicant becomes a linked Odoo employee. |
| HR-002 | The system shall support recruitment from approved vacancy through application, review, interview, requirements, and employment. | Must | One applicant completes the demonstrable recruitment lifecycle. |
| HR-003 | Applicants shall have secure status tracking and access only to their own records. | Must | A verified applicant sees their status, timeline, interviews, and visible document requests. |
| HR-004 | The system shall support interview scheduling and interviewer appraisal. | Must | Scheduling creates a Calendar event and ADM-4 appraisal request. |
| HR-005 | The system shall collect typed pre-employment data and attachments. | Must | ADM-3 and ADM-5 data and uploaded evidence are stored against the application. |
| HR-006 | The system shall record attendance. | Should | A sample employee has check-in or attendance records and a summary. |
| HR-007 | The system shall support performance evaluations and review history. | Should | A sample employee evaluation has criteria, reviewer, period, and result. |
| HR-008 | Recruitment demand shall trace back to an approved manpower need when applicable. | Must | A vacancy created from crew shortage retains its manpower-request source. |

### 9.10 Document Control

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| DOC-001 | The system shall maintain a controlled document catalogue with code, title, department, category, version, owner, and status. | Must | Representative controlled records are searchable by code and category. |
| DOC-002 | A document template shall define typed fields, required fields, selections, attachments, and signatures. | Must | A request renders fields appropriate to the selected template and validates required values. |
| DOC-003 | The system shall support document requests, submission, review, approval, rejection, due date, and responsibility. | Must | A representative form completes the controlled workflow. |
| DOC-004 | The catalogue shall include contracts, vessel certificates, insurance, permits, board resolutions, and ISO documents. | Must | At least one representative record per category is visible and organized. |
| DOC-005 | Documents with validity periods shall expose expiry and renewal status. | Must | Expiring vessel, crew, insurance, or permit records appear in an exception view. |
| DOC-006 | Approved source forms shall be preserved without omitting visible content. | Must | The approved source file and its extracted typed definition are both accessible. |
| DOC-007 | Future DocuSign integration shall preserve signed evidence and status. | Future | A mock or live envelope reference is linked to a controlled document. |

### 9.11 Marketing and Customer Management

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| MKT-001 | The system shall maintain client organizations, contacts, vessels, service history, and Client Tariffs. | Must | A client dashboard displays requests and related commercial master data. |
| MKT-002 | Customer Relations shall create, review, and monitor client Service Orders. | Must | Internal intake uses normalized fields and displays operational progress. |
| MKT-003 | The system should support opportunities, quotations, communication history, and client follow-up through Odoo CRM. | Should | A sample opportunity links to a client and resulting Service Order. |
| MKT-004 | Client-visible data shall exclude internal-only notes, cost, HR, and safety information. | Must | Portal ownership and visibility rules prevent unauthorized access. |

### 9.12 Corporate and Executive Management

| ID | Requirement | Priority | Demonstration acceptance |
| --- | --- | --- | --- |
| MGT-001 | The system shall provide management KPIs for finance, fleet utilization, vessel availability, maintenance, HSSE, crewing, and profitability. | Must | One executive dashboard presents representative cross-functional KPIs with drill-down sources. |
| MGT-002 | The system shall distinguish revenue from profitability by including attributable operating cost. | Should | A sample Service Order compares billed revenue with selected cost categories. |
| MGT-003 | The system shall manage board resolutions, contracts, insurance, legal cases, and internal-audit records. | Must | Representative corporate records show owner, dates, status, attachments, and actions. |
| MGT-004 | The system shall provide exception indicators for overdue actions, expiring documents, unavailable tugboats, crew shortages, open incidents, and uninvoiced completed services. | Must | An executive user can open each exception from a summary. |
| MGT-005 | Power BI may consume governed Odoo data for executive reporting. | Future | A documented dataset or mock report identifies source models and refresh status. |

## 10. Cross-Module Data Requirements

| Data object | Authoritative owner | Main consumers |
| --- | --- | --- |
| Client and contact | Customer Relations / shared Odoo partner | Service Orders, tariffs, invoices, CRM, portal |
| Assisted vessel | Marine Operations | Service Orders, operations, HSSE, documents |
| Tugboat | Marine Operations / Technical | Scheduling, maintenance, inventory, AIS, KPIs |
| Employee | HR | Crewing, payroll, training, maintenance labor, approvals |
| Crew profile and certificates | Crewing | Readiness, scheduling, HSSE, HR |
| Service Order | Customer Relations / Marine Operations | Dispatch, crewing, billing, client portal, KPIs |
| Marine Operation | Operations | Client updates, HSSE, fuel, billing, performance |
| Client Tariff | Accounting Manager | Quotation, rate freezing, Billing Review |
| Invoice and payment | Odoo Accounting | Service Order billing status, cash reporting, management |
| Product and stock quantity | Inventory | Maintenance, procurement, dispatch, cost reporting |
| Work order and equipment history | Technical | Tug availability, procurement, inventory, management |
| Incident and corrective action | HSSE | Operations, training, management, audit |
| Controlled document | Document Control / owning department | Compliance, HR, vessels, corporate governance |
| Applicant and vacancy | HR | Careers, interviews, documents, employee conversion |

## 11. Dashboard Requirements

The demonstration should provide role-specific views rather than one unrestricted dashboard.

| Dashboard | Required content |
| --- | --- |
| Client | Service Orders, schedule, status, authorized activity updates, and related documents. |
| Customer Relations | New requests, pending review, pricing exceptions, client activity, and upcoming services. |
| Operations | Service Order pipeline, tug schedule, readiness blockers, active Marine Operations, and delays. |
| Crewing | assignments, shortages, expiring certificates, medicals, leave, and manpower actions. |
| Technical | due maintenance, open defects, unavailable tugboats, dry-dock milestones, and parts shortages. |
| HSSE | incidents, near misses, inspections, high risks, overdue actions, permits, and training expiry. |
| HR | vacancies, applicants by stage, interviews, document requirements, overdue actions, and hires. |
| Finance | Billing Review, Pricing Exceptions, draft and posted invoices, unpaid amounts, and payments. |
| Executive | revenue, cash indicators, utilization, availability, maintenance status, HSSE metrics, staffing, and profitability. |

## 12. Non-Functional Demonstration Requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | The demonstration shall run on Odoo 19 through the shared Docker configuration. |
| NFR-002 | Navigation and labels shall use the canonical SEDAR business terms. |
| NFR-003 | Forms shall use normalized selections where controlled values reduce errors. |
| NFR-004 | Required fields and state transitions shall be validated server-side. |
| NFR-005 | Portal users shall see only records owned by their client or applicant identity. |
| NFR-006 | Important approvals, submissions, completions, and confirmations shall capture user and time. |
| NFR-007 | Demo fixtures shall be fictional, repeatable, and separable from production-oriented models. |
| NFR-008 | No demonstration feature shall claim production compliance without SEDAR and specialist validation. |
| NFR-009 | The UI shall remain usable on common desktop and mobile portal viewports. |
| NFR-010 | Required addons shall install or upgrade without Odoo registry, model, access, or XML errors. |

## 13. Demonstration Acceptance Scenarios

The baseline demonstration is accepted when the project team can show:

1. A client submits a Service Order with normalized service, vessel, Terminal, schedule, and tug requirements.
2. Operations resolves tug, crew, certificate, and inventory readiness with visible blockers.
3. A Ready Service Order creates a Marine Operation and records actual activity through Service Completion.
4. Finance reviews actual quantities and creates a standard Odoo invoice that can be posted and paid.
5. A genuine crew shortage creates an approved vacancy, while medical, certificate, and leave shortages follow non-hiring actions.
6. A published vacancy accepts an ADM-3 application and creates secure applicant tracking.
7. HR processes the applicant through interview, ADM-4, ADM-5, and employee conversion.
8. A maintenance work order affects tug availability and consumes a spare part.
9. An HSSE incident or inspection produces an assigned corrective action.
10. A Purchase Request with product-level Line Awards becomes the correct supplier-grouped Purchase Orders, receipts, stock updates, and supplier bills.
11. Controlled corporate, vessel, crew, HR, and compliance documents are organized with validity and status.
12. An executive dashboard summarizes representative financial, operational, technical, HSSE, crewing, and HR indicators.

## 14. Assumptions Requiring SEDAR Confirmation

- One Service Order represents one billable tug assist or move at one Terminal.
- The Tug Master has authority to declare completion for the assigned tugboat.
- Scheduled service date selects the Client Tariff and client confirmation freezes the rate.
- Multi-tug billing records actual time per participating tugboat.
- Manual Billing Adjustments are allowed until approved formulas are supplied.
- Crew compliance requirements vary by rank, service, tug class, and regulation.
- Maintenance intervals, critical equipment, dry-dock rules, and spare-part policies will be provided during discovery.
- HSSE classifications, risk matrix, notification thresholds, and statutory reports will be confirmed by SEDAR.
- Procurement approval limits, supplier qualification, inventory valuation, and warehouse structure are not yet confirmed.
- Payroll rules, attendance devices, benefits, and Philippine statutory configuration require specialist validation.
- Executive KPI formulas and profitability cost allocation require management approval.

## 15. Recommended Delivery Sequence

1. Preserve and stabilize the current client-to-payment and shortage-to-employment demonstrations.
2. Add maintenance and equipment history because tug availability is a direct dispatch dependency.
3. Add inventory and fuel records, replacing manual Inventory Readiness Confirmation.
4. Add procurement connected to maintenance and inventory demand.
5. Add HSSE and compliance workflows connected to operations, crew, and documents.
6. Expand standard Finance, HR attendance, performance, payroll inputs, and corporate records.
7. Build cross-functional executive KPIs and optional Power BI integration.
8. Add live AIS/GPS, Microsoft 365, SharePoint, DocuSign, barcode, bank, and other approved integrations.

## 16. Change Control

This PRD is the demonstration baseline. A requirement may be clarified through discovery without implying that unconfirmed production rules have already been accepted. Consequential architecture changes must be recorded in a new Architecture Decision Record. Changes to canonical domain terms must be agreed before updating `CONTEXT.md`.

# MVP Module Content Specification

Source of truth: `resources/Web System.pdf`

Note: `resources/Web System.txt` currently exists but is empty, so this plan uses the already extracted project documents: `PDF_ANALYSIS.md` and `DASHBOARD_COVERAGE_MATRIX.md`.

This document defines what every MVP tab should display, do, and execute from the viewpoint of a tugboat company owner or president.

## Strict Scope Rule

- Include every module and subitem stated in the PDF.
- Do not add extra top-level modules beyond the PDF.
- Supporting records such as vessels, customers, jobs, suppliers, crew, invoices, and documents are allowed only inside the PDF modules.
- SEDAR-specific rates, approvals, forms, payroll rules, billing logic, and real document templates remain placeholders until post-deal discovery.

## External Benchmark Notes

Public maritime software confirms that these are normal areas for a tug or marine operations system:

- Helm Operations publicly references maintenance, compliance, inventory, requisitions, personnel, jobs, invoicing, and corrective actions.
- Ripple Operations publicly references maritime business support, crew management, crew payroll and finance, skill assessment, and data collection and compliance reporting.

These sources are only benchmarks for shaping the content inside the PDF modules. They do not add new modules.

Sources:

- https://www.helmoperations.com/
- https://www.rippleoperations.com/

## Required Top-Level Tabs

The MVP should use these exact document-backed tabs:

1. Management Dashboard
2. Finance and Accounting
3. Tug Operations
4. Technical and Maintenance
5. Health, Safety, and Environment
6. Crewing
7. Procurement
8. Inventory
9. Human Resources
10. Document Control

Implementation cleanup:

- `SEDAR Dashboard` may remain as the landing screen only if it is treated as the `Management Dashboard`.
- `Marine Operations` should be renamed to `Tug Operations`.
- `HSSE` should be renamed to `Health, Safety, and Environment` unless abbreviated only for compact layout.
- `Fleet Management` should not remain as a separate top-level module under the strict rule. Vessel data belongs inside `Tug Operations`, `Technical and Maintenance`, and `Management Dashboard`.
- `Management Reports` should be renamed or merged into `Management Dashboard`.

## 1. Management Dashboard

PDF coverage:

- KPIs
- Financial reports
- Utilization
- Vessel availability
- Profitability

Owner question:

- Are our vessels, people, customers, cash, and safety controls producing profitable and reliable service today?

What this tab should display:

- Executive KPI cards: revenue this month, gross margin, cash position, AR aging, AP aging, jobs completed, jobs delayed, fleet utilization, vessel availability, maintenance downtime, HSE open actions, crew compliance risk, inventory risk, procurement bottlenecks, HR actions due, document expiry risk.
- Financial report summary: revenue, expenses, margin, budget variance, cash flow, receivables, payables.
- Utilization summary: each tug's job hours, idle hours, standby hours, and utilization percentage.
- Vessel availability summary: available, assigned, under maintenance, dry dock, off-hire.
- Profitability views: by vessel, customer, and job type.
- Risk panel: overdue maintenance, expiring crew documents, low stock, pending purchase approvals, expiring certificates, open corrective actions.

What this tab should do:

- Open the source records behind every KPI.
- Filter by date range, vessel, customer, and job type.
- Show green, watch, and risk status per business area.
- Provide the president one screen that answers where money, operations, compliance, and readiness need attention.

Required sample data:

- KPI records, vessels, customers, jobs, voyage logs, finance records, crew records, maintenance work orders, HSE records, inventory items, procurement records, HR records, and controlled documents.

MVP drill-downs:

- Financial report
- Vessel utilization and availability
- Customer profitability
- Vessel profitability
- Job type profitability
- KPI source records

## 2. Finance and Accounting

PDF coverage:

- General Ledger
- Accounts Payable
- Accounts Receivable
- Budgeting
- Cash Flow
- Fixed Assets
- Payroll

Owner question:

- Are we billing everything, collecting on time, controlling costs, and protecting cash?

What this tab should display:

- General ledger summary by account group using sample categories.
- Accounts receivable aging: current, 1-30, 31-60, 61-90, over 90 days.
- Accounts payable aging by supplier and due date.
- Budget versus actual by month and expense category.
- Cash flow position: opening cash, receipts, payments, ending cash, and next 30-day obligations.
- Fixed asset register summary: vessels, equipment, vehicles, tools, and book value placeholders.
- Payroll summary: crew payroll, office payroll, overtime estimate, and payroll integration placeholder.
- Towage billing queue: completed jobs not yet billed, billed jobs not yet paid, and billing exceptions.

What this tab should do:

- View sample invoice and accounting records linked to tug jobs.
- Mark invoice status as draft, open, overdue, or paid.
- Show unbilled completed jobs so missed billing is visible.
- Link revenue and cost back to vessel, customer, and job type profitability.
- Represent every accounting subitem even if production accounting posting is not yet implemented.

Required fields:

- Record type, document number, customer, supplier, linked job, amount, invoice date, due date, aging bucket, status, budget category, cash impact, asset category, payroll group, notes.

MVP drill-downs:

- Invoice list
- Customer receivables
- Supplier payables
- Budget line items
- Cash flow entries
- Fixed asset register
- Payroll summary

## 3. Tug Operations

PDF coverage:

- Job dispatch
- Tug scheduling
- Voyage logs
- Fuel monitoring
- Towage billing
- GPS/AIS tracking

Owner question:

- Are we dispatching the right tug and crew, completing jobs on time, logging billable work, and seeing where our vessels are?

What this tab should display:

- Dispatch board: requested, quoted, approved, scheduled, dispatched, in progress, completed, billed, paid, cancelled.
- Tug schedule by vessel and date.
- Voyage log summary: start, end, voyage hours, waiting hours, standby hours, delay reason, remarks.
- Fuel monitoring: fuel used per job, fuel used per vessel, and variance against expected consumption.
- Towage billing readiness: completed jobs missing billing, waiting time to bill, standby time to bill, direct cost, gross margin.
- GPS/AIS placeholder: last known vessel location, timestamp, and source marked as sample data.

What this tab should do:

- Create a job order from a customer request.
- Assign tug, schedule, route, origin, destination, and service type.
- Move jobs through dispatch statuses.
- Create voyage and fuel logs against completed jobs.
- Flag delays and unbilled jobs.
- Feed billing, profitability, vessel utilization, and fuel KPIs.

Required fields:

- Job number, customer, service type, requested datetime, scheduled datetime, assigned vessel, origin, destination, status, delay reason, actual start, actual end, voyage hours, waiting hours, fuel used, billable amount, direct cost, gross margin, last known location.

MVP drill-downs:

- Job order detail
- Dispatch assignment
- Tug schedule
- Voyage log
- Fuel log
- Billing source job
- GPS/AIS placeholder table

## 4. Technical and Maintenance

PDF coverage:

- Planned Maintenance System
- Dry docking
- Work orders
- Spare parts
- Equipment history

Owner question:

- Which vessels or equipment can interrupt operations, create downtime, or require urgent spending?

What this tab should display:

- Planned maintenance due soon and overdue.
- Dry docking schedule by vessel, date window, status, budget placeholder, and readiness status.
- Work orders by status: open, waiting parts, in progress, done, overdue.
- Critical spare parts linked to open work orders.
- Equipment history: repeat defects, last service date, downtime hours, cost trend.
- Vessel maintenance risk by severity.

What this tab should do:

- Create planned maintenance, defect, and dry dock work orders.
- Link work orders to vessel and equipment.
- Record downtime hours, estimated cost, severity, due date, and status.
- Reference required spare parts and signal procurement or inventory risk.
- Update vessel availability and management dashboard risk.

Required fields:

- Work order number, vessel, equipment, work type, severity, due date, downtime hours, cost, status, spare parts note, equipment history, dry dock window, assigned owner.

MVP drill-downs:

- Work order detail
- Vessel maintenance profile
- Planned maintenance list
- Dry dock plan
- Spare parts used
- Equipment history

## 5. Health, Safety, and Environment

PDF coverage:

- Incident reporting
- Inspections
- Permits
- Audits
- Risk assessments
- Training records

Owner question:

- Are we operating safely, staying compliant, and closing corrective actions before they become customer or regulator issues?

What this tab should display:

- Incidents this month and year to date.
- Near misses and unsafe condition records.
- Inspection findings by vessel and status.
- Permit register with expiry and renewal status.
- Audit findings by status and responsible person.
- Risk assessment list by vessel, job, risk level, and mitigation status.
- Training record compliance summary.
- Open and overdue corrective actions.

What this tab should do:

- Record incident, near miss, inspection, permit, audit, risk assessment, and training records.
- Assign corrective action, responsible person, due date, and status.
- Link HSE events to vessel and job when applicable.
- Escalate overdue actions to the management dashboard.
- Show compliance readiness for customer or regulator review.

Required fields:

- HSE record number, record type, vessel, job, event date, risk level, responsible person, corrective action, due date, status, training participant, permit expiry, audit reference.

MVP drill-downs:

- Incident detail
- Inspection record
- Permit register
- Audit finding
- Risk assessment
- Training record
- Corrective action list

## 6. Crewing

PDF coverage:

- Crew scheduling
- Certifications
- STCW documents
- Medicals
- Leave
- Payroll integration

Owner question:

- Do we have enough qualified and medically cleared crew to safely accept and execute upcoming tug jobs?

What this tab should display:

- Crew availability: available, assigned, on leave, training.
- Crew schedule by vessel and upcoming job.
- Certification status: valid, expiring soon, expired.
- STCW expiry list.
- Medical expiry list.
- Leave calendar and unavailable crew.
- Payroll integration summary placeholder: payroll group, overtime estimate, pending payroll export.

What this tab should do:

- Maintain crew profiles and assignment status.
- Assign crew to vessel or scheduled job using sample scheduling.
- Track certifications, STCW, medicals, training, and leave.
- Warn when crew is unavailable or documents are expired.
- Feed payroll summary and crew compliance risk to the management dashboard.

Required fields:

- Crew name, rank, vessel, availability, schedule, certificate type, STCW expiry, medical expiry, training expiry, leave dates, payroll group, compliance status.

MVP drill-downs:

- Crew profile
- Crew schedule
- Certificate register
- STCW register
- Medical record
- Leave record
- Payroll integration summary

## 7. Procurement

PDF coverage:

- Purchase requests
- Purchase orders
- Supplier management
- Approval workflow

Owner question:

- Are purchasing delays, supplier performance, or approval bottlenecks preventing vessels from working?

What this tab should display:

- Purchase requests by status: draft, pending approval, approved, ordered, received.
- Purchase orders by supplier, amount, status, and expected delivery.
- Supplier management summary: supplier, item category, lead time, delivery reliability, pending invoices.
- Approval workflow view: request owner, approval owner, amount, age in approval, next action.
- Urgent requests linked to maintenance or critical inventory.

What this tab should do:

- Create purchase request and purchase order records.
- Link procurement to maintenance work orders and low-stock inventory.
- Assign approval owner and show pending approval age.
- Mark purchase orders as ordered or received.
- Feed procurement bottleneck and supplier performance metrics to the management dashboard.

Required fields:

- PR or PO number, record type, supplier, requested by, request date, amount, status, approval owner, maintenance link, inventory link, expected delivery, notes.

MVP drill-downs:

- Purchase request detail
- Purchase order detail
- Supplier profile
- Approval history
- Maintenance-linked procurement
- Stock reorder signal

## 8. Inventory

PDF coverage:

- Spare parts
- Fuel
- Lubricants
- Office supplies
- Warehouse management
- Barcode support

Owner question:

- Do we have the critical stock, fuel, and supplies needed to keep tugs running without tying up too much cash?

What this tab should display:

- Spare parts inventory by vessel relevance, quantity, reorder point, and critical status.
- Fuel stock or fuel consumption summary.
- Lubricant stock or consumption summary.
- Office supplies summary.
- Warehouse management list: warehouse, location/bin placeholder, quantity on hand, stock value.
- Barcode support placeholder: item barcode field and scan-ready status.
- Low stock and critical stock alerts.

What this tab should do:

- Maintain inventory item records.
- Calculate stock value from quantity and unit cost.
- Compare quantity on hand against reorder point.
- Flag low and critical stock.
- Link critical spare parts to maintenance and procurement.
- Show barcode support as a demo-ready field, not a production scanner integration.

Required fields:

- Item name, category, warehouse, location/bin placeholder, barcode, quantity on hand, reorder point, unit cost, stock value, status, linked maintenance demand, linked procurement request.

MVP drill-downs:

- Inventory item detail
- Stock movement placeholder
- Warehouse stock list
- Reorder list
- Fuel record
- Lubricant record
- Barcode support placeholder

## 9. Human Resources

PDF coverage:

- Employee records
- Attendance
- Performance evaluation
- Recruitment

Owner question:

- Are our office and operations staff complete, present, performing, and being recruited where gaps exist?

What this tab should display:

- Employee records summary by department and status.
- Attendance summary: present, absent, late, pending review.
- Performance evaluation due list.
- Recruitment pipeline: open roles, candidates, stage, urgency.
- HR actions due: missing records, attendance exceptions, overdue evaluations, recruitment bottlenecks.
- Marine crew link for crew records that also affect HR or payroll.

What this tab should do:

- Maintain HR records for employees, attendance, performance, and recruitment.
- Track HR status and due actions.
- Link crew records where crew is part of employee or payroll reporting.
- Feed management dashboard with HR action due count.

Required fields:

- Employee or HR record name, department, record type, status, summary, attendance date, attendance status, evaluation due date, recruitment role, recruitment stage.

MVP drill-downs:

- Employee profile
- Attendance record
- Performance evaluation record
- Recruitment pipeline
- Crew/HR link

## 10. Document Control

PDF coverage:

- Contracts
- Vessel certificates
- Insurance
- Permits
- Board resolutions
- ISO documents

Owner question:

- Which documents can stop operations, weaken compliance, or create legal exposure if not renewed?

What this tab should display:

- Contracts register with status and renewal owner.
- Vessel certificates register with vessel, expiry date, and renewal status.
- Insurance register with expiry and owner.
- Permits register with expiry and owner.
- Board resolutions register with version and status.
- ISO document register with version, owner department, and status.
- Documents pending renewal, expired documents, and documents due in 30/60/90 days.

What this tab should do:

- Maintain controlled document records across all PDF document types.
- Track owner department, vessel link, expiry date, renewal owner, version, and status.
- Flag documents for renewal or expired.
- Feed document expiry risk to the management dashboard.
- Provide placeholders for version history and approval status until the real document repository is chosen.

Required fields:

- Document name, document type, owner department, vessel, expiry date, renewal owner, status, version, approval status placeholder, document link placeholder.

MVP drill-downs:

- Document detail
- Version history placeholder
- Renewal owner list
- Approval status placeholder
- Vessel certificate context

## Cross-Module Demo Flow

The first demo should prove that all PDF modules can connect through sample data without claiming SEDAR-specific process confirmation.

1. `Tug Operations` creates a customer tug job.
2. `Crewing` confirms available and qualified crew.
3. `Technical and Maintenance` confirms assigned vessel availability.
4. `Inventory` confirms fuel, lubricant, and critical spare readiness.
5. `Procurement` shows any pending request if a part is low.
6. `Health, Safety, and Environment` shows permit, risk, inspection, and training readiness.
7. `Tug Operations` records voyage hours, waiting time, fuel use, and completion.
8. `Finance and Accounting` shows towage billing, AR, cash, budget, fixed asset, and payroll summaries.
9. `Document Control` shows contracts, vessel certificates, insurance, permits, board resolutions, and ISO documents.
10. `Management Dashboard` summarizes KPIs, financial reports, utilization, vessel availability, and profitability.

## Exact PDF Coverage Checklist

Finance and Accounting:

- [ ] General Ledger
- [ ] Accounts Payable
- [ ] Accounts Receivable
- [ ] Budgeting
- [ ] Cash Flow
- [ ] Fixed Assets
- [ ] Payroll

Tug Operations:

- [ ] Job dispatch
- [ ] Tug scheduling
- [ ] Voyage logs
- [ ] Fuel monitoring
- [ ] Towage billing
- [ ] GPS/AIS tracking

Technical and Maintenance:

- [ ] Planned Maintenance System
- [ ] Dry docking
- [ ] Work orders
- [ ] Spare parts
- [ ] Equipment history

Health, Safety, and Environment:

- [ ] Incident reporting
- [ ] Inspections
- [ ] Permits
- [ ] Audits
- [ ] Risk assessments
- [ ] Training records

Crewing:

- [ ] Crew scheduling
- [ ] Certifications
- [ ] STCW documents
- [ ] Medicals
- [ ] Leave
- [ ] Payroll integration

Procurement:

- [ ] Purchase requests
- [ ] Purchase orders
- [ ] Supplier management
- [ ] Approval workflow

Inventory:

- [ ] Spare parts
- [ ] Fuel
- [ ] Lubricants
- [ ] Office supplies
- [ ] Warehouse management
- [ ] Barcode support

Human Resources:

- [ ] Employee records
- [ ] Attendance
- [ ] Performance evaluation
- [ ] Recruitment

Document Control:

- [ ] Contracts
- [ ] Vessel certificates
- [ ] Insurance
- [ ] Permits
- [ ] Board resolutions
- [ ] ISO documents

Management Dashboard:

- [ ] KPIs
- [ ] Financial reports
- [ ] Utilization
- [ ] Vessel availability
- [ ] Profitability

## Build Order From This Plan

1. Rename top-level navigation to the exact PDF module names.
2. Merge or relabel any extra top-level app areas that are not PDF modules.
3. Replace generic dashboard cards with owner-facing KPI cards from this document.
4. Add one list, form, and dashboard summary per PDF module.
5. Seed sample records for every checklist item.
6. Add drill-down links from KPI cards to source records.
7. Run the cross-module demo flow and verify every checklist item appears on screen.


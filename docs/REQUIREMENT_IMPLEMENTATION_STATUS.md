# Requirement Implementation Status

Updated: July 10, 2026

This file tracks the client requirements from `resources/Web System.txt`. It describes backend behavior, not just visible menus or sample records.

Status meanings:

- **Working**: the main backend flow exists and was verified.
- **Partial**: useful backend behavior exists, but an important part is still missing.
- **Missing**: no dependable backend flow exists yet.

## Finance and Accounting

| Requirement | Status | Current backend and gap |
|---|---|---|
| General Ledger | Partial | Native Odoo Community journal entries and journal items work. Full Trial Balance, Balance Sheet, Profit and Loss, and Cash Flow reports are missing. |
| Accounts Payable | Working | Native vendor bills and payments work. Purchase bills can carry SEDAR job, vessel, and budget links. |
| Accounts Receivable | Working | Native customer invoices and payments work. Towage billing creates linked customer invoices. |
| Budgeting | Partial | Department budgets calculate planned, committed, actual, available, and use percentage. Budget assignment and approval access still need a production process. |
| Cash Flow | Partial | Manual inflow and outflow forecasts and 30-day totals work. Automatic forecasts and a formal cash-flow statement are missing. |
| Fixed Assets | Partial | Asset register, straight-line schedule, and depreciation journal posting work. Purchase capitalization and disposal accounting are missing. |
| Payroll | Partial | Crew hours, rates, overtime, approval, and job-cost allocation work. Payslips, deductions, Philippine taxes, payroll payments, and payroll journal posting are missing. |

## Tug Operations

| Requirement | Status | Current backend and gap |
|---|---|---|
| Job dispatch | Working | Request, readiness check, dispatch, start, completion, billing, and invoice links work. |
| Tug scheduling | Working | Vessel schedules and state changes work. Invalid dates and overlapping active assignments are blocked. |
| Voyage logs | Working | Job and vessel links, departure, arrival, distance, and calculated duration work. Invalid times and distance are blocked. |
| Fuel monitoring | Working | Vessel, job, voyage, liters, cost, and cost per liter work. Invalid quantities and costs are blocked. Fuel stock consumption is still separate. |
| Towage billing | Working | Completed jobs create linked draft customer invoices and invoice posting updates the job state. |
| GPS/AIS tracking | Partial | Position history, coordinates, speed, course, source, current vessel position, and stale-message protection work. A live AIS/GPS provider connection is missing. |

## Technical and Maintenance

| Requirement | Status | Current backend and gap |
|---|---|---|
| Planned Maintenance System | Partial | Native Community maintenance requests and schedules are used. Meter triggers, reusable job plans, and detailed checklists are missing. |
| Dry docking | Partial | Dry-dock dates, blocking state, downtime, and costs exist. Scope, milestones, contractors, and dock project control are missing. |
| Work orders | Working | Native maintenance requests are linked to vessels, severity, costs, downtime, parts, RFQs, receipts, and dispatch blocking. |
| Spare parts | Working | Native products, stock availability, shortages, RFQs, receipts, warehouse-to-vessel issues, and work-order consumption moves are linked. |
| Equipment history | Partial | Native equipment and maintenance request history work. Meter readings and a locked service-history ledger are missing. |

## HSE

| Requirement | Status | Current backend and gap |
|---|---|---|
| Incident reporting | Working | Incidents, investigation state, owners, corrective actions, and closure checks work. |
| Inspections | Working | Inspection headers, checklist lines, findings, finish, and closure checks work. |
| Permits | Working | Permit dates, expiry state, renewal, review, approval, and attachment checks work. |
| Audits | Partial | Audits can be recorded as an inspection type. Audit plans, evidence, and formal sign-off are missing. |
| Risk assessments | Working | Hazard, risk scoring, controls, review, and mitigation states work. |
| Training records | Working | Course, employee, completion, expiry, certificate, and renewal data work. Attendance results and reminders need more depth. |

## Crewing

| Requirement | Status | Current backend and gap |
|---|---|---|
| Crew scheduling | Partial | Crew roster and rotations work. Rank requirements, headcount, and rotation-overlap checks are missing. |
| Certifications | Working | Crew certificates and expiry checks work and can block dispatch. Issuer and verification controls need more depth. |
| STCW documents | Partial | STCW certificates can be recorded as certification types. A controlled STCW type list and document verification are missing. |
| Medicals | Working | Medical dates, expiry, and fit-for-duty status work and can block dispatch. |
| Leave | Partial | Leave request states and date validation work. Native HR leave, balance, and rotation conflict checks are missing. |
| Payroll integration | Partial | Crew payroll references and approved job-cost allocations work. Full payroll export, posting, and payment are missing. |

## Procurement

| Requirement | Status | Current backend and gap |
|---|---|---|
| Purchase Requests | Working | Product request lines, budget checks, submit, approve, reject, accredited supplier selection, native RFQ conversion, ordering, and receipt status work. |
| Purchase Orders | Working | Native Community RFQs and purchase orders are used with budget, vessel, maintenance, canvassing, and receipt links. |
| Supplier management | Working | Native suppliers include accreditation, discount, reliability, and quote comparison data. |
| Approval workflow | Working | Purchase Manager approval, rejection reasons, budget and canvassing checks, supplier accreditation, and permanent request history work. |

## Inventory

| Requirement | Status | Current backend and gap |
|---|---|---|
| Spare parts | Working | Native products, quantities, warehouses, receipts, and reorder signals work. |
| Fuel and lubricants | Working | Native stock products can be issued to vessel locations, and operational fuel logs create linked vessel consumption moves. |
| Office supplies | Working | Native stock products and categories support office supplies. |
| Warehouse management | Working | Native Community warehouses, locations, stock moves, receipts, and transfers are used. |
| Barcode support | Partial | Native product barcodes exist. A verified scanner workflow is not configured. |

## Human Resources

| Requirement | Status | Current backend and gap |
|---|---|---|
| Employee records | Working | Native Community employees are linked to SEDAR crew and document data. |
| Attendance | Missing | Current attendance data is a placeholder and is not backed by native check-in and check-out records. |
| Performance evaluation | Missing | Current performance data is a placeholder with no review cycle, scoring, or history. |
| Recruitment | Working | Native applicants are used with job dispatch, interview checks, assessment, attachments, and hiring stages. |

## Document Control

| Requirement | Status | Current backend and gap |
|---|---|---|
| Contracts | Working | Contract records, dates, status, owner, and attachments work. |
| Vessel certificates | Working | Vessel links, issue and expiry dates, renewal status, and expiry checks work. |
| Insurance | Working | Policy, insurer, coverage, dates, attachments, and expiry checks work. |
| Permits | Working | Document permits and HSE operating permits are supported. |
| Board resolutions | Working | Board resolution records and attachments work. |
| ISO documents | Partial | ISO records, attachments, approval, and version renewal work. Retention, locked revision history, and role rules are missing. |

## Management Dashboard

| Requirement | Status | Current backend and gap |
|---|---|---|
| KPIs | Partial | Live job, vessel, HSE, document, maintenance, finance, asset, and profit values exist. More time-based trends and targets are missing. |
| Financial reports | Partial | Revenue, receivables, payables, cash, forecasts, unbilled work, assets, and job profit are calculated. Formal statements are missing. |
| Utilization | Partial | A basic vessel measure exists. Job-hour and available-hour utilization is missing. |
| Vessel availability | Partial | Vessel and maintenance blocking states exist. A time-based availability percentage is missing. |
| Profitability | Working | Posted revenue, fuel, vendor bills, crew cost, total cost, gross profit, and margin are calculated per job. |

## Known Migration Issue

The database currently contains one legacy voyage row without a job link. It comes from the older duplicate model in `sedar_marine_mvp`. It must be mapped or archived during a planned migration rather than changed without an owner decision.

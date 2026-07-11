# Requirement Implementation Status

Updated: July 11, 2026

This file tracks the client requirements from `resources/Web System.txt`. It describes backend behavior, not just visible menus or sample records.

Status meanings:

- **Working**: the main backend flow exists and was verified.
- **Partial**: useful backend behavior exists, but an important part is still missing.
- **Missing**: no dependable backend flow exists yet.

## Finance and Accounting

| Requirement | Status | Current backend and gap |
|---|---|---|
| General Ledger | Working | OCA General Ledger and Trial Balance reports work from native journal items with date, posting state, account, partner, journal, analytic, hierarchy, and currency filters; running balances, drill-down links, and HTML, PDF, and XLSX output were verified. |
| Accounts Payable | Working | Native vendor bills and payments work. Cash/check release requires an approved PO and matching posted bill; vouchers carry supplier, vessel, job, maintenance, and check-clearing links. |
| Accounts Receivable | Working | Approved client/terminal/service tariffs calculate towage billing and post linked customer invoices. Collections match the correct invoice and bank, while bounced receipts reopen the invoice. |
| Budgeting | Partial | Department budgets calculate planned, committed, actual, available, and use percentage. Budget assignment and approval access still need a production process. |
| Cash Flow | Working | OCA Cash Flow uses open accounting items and forecast lines. Per-bank statement, book, outstanding-check, and available-cash figures support daily cash control. Live bank feeds remain external. |
| Fixed Assets | Partial | Asset register, straight-line schedule, and depreciation journal posting work. Purchase capitalization and disposal accounting are missing. |
| Payroll | Partial | Crew hours, rates, overtime, approval, and job-cost allocation work. Payslips, deductions, Philippine taxes, payroll payments, and payroll journal posting are missing. |
| Finance operations | Working | Petty cash auto-posting, employee advances, oldest-first liquidation, PO-backed disbursements, check status, tariff billing, rebates, collections, bank adjustments, and role-based approvals use the native ledger. |
| Financial statements | Working | General Ledger, Trial Balance, comparative Profit and Loss, comparative Balance Sheet, Cash Flow, and customer/supplier statements provide browser, PDF, and XLSX reporting through OCA modules. |

> **Demo-only access warning:** Every internal user currently receives the Finance Manager role so the controlled MVP demo can use all finance screens without user setup. Remove this automatic role before pilot testing, client access, production use, or loading real financial data; assign Cashier, Finance Officer, and Finance Manager roles to named users instead.

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
| Planned Maintenance System | Working | Native Community work orders now support reusable plans, daily calendar triggers, running-hour meters, copied checklists and parts, labor costs, and automatic next-due advancement. |
| Dry docking | Partial | Dry-dock dates, blocking state, downtime, and costs exist. Scope, milestones, contractors, and dock project control are missing. |
| Work orders | Working | Native maintenance requests are linked to vessels, severity, costs, downtime, parts, RFQs, receipts, and dispatch blocking. |
| Spare parts | Working | Native products, stock availability, shortages, RFQs, receipts, warehouse-to-vessel issues, and work-order consumption moves are linked. |
| Equipment history | Working | Native equipment history includes permanent running-hour readings and a locked completion snapshot with work, downtime, labor, parts, meter, and total cost. |

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
| Crew scheduling | Working | Crew roster and rotations work with date validation, overlap blocking, verified-document checks, and vessel assignment. |
| Certifications | Working | Crew certificates and expiry checks work and can block dispatch. Issuer and verification controls need more depth. |
| STCW documents | Working | Controlled STCW types, certificate number, issuer, dates, attachment, verification owner, and dispatch checks work. |
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
| Attendance | Working | Native Community check-in and check-out records now support office, standby, and vessel shifts, job links, overtime calculation, and HR approval. |
| Performance evaluation | Working | Review cycles, employee and manager stages, weighted goals, scores, comments, HR approval, and permanent results work. |
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

# SEDAR Finance MVP Implementation Plan

## Goal

Show one reliable path from a client-requested tug service to a paid customer invoice. The custom SEDAR workflow will calculate and review the charge. Odoo Accounting will own the invoice, receivable, payment, and ledger records.

The plan is based on the Canva workflow, the finance interview transcript, the current Odoo 19 code, and mock data from commit `a476332`.

## Confirmed workflow

1. A client requests one tug assist or move at one terminal through a Service Order.
2. Marketing reviews the request and resolves a matching Client Tariff using the client, terminal, service or move, tug class when applicable, and scheduled service date.
3. The system freezes the selected pricing basis, unit rate, minimum charge, currency, and tariff reference when the client confirms the Service Order.
4. The automated Dispatch Readiness Gate checks tugboat and crew readiness plus an audited manual Inventory Readiness Confirmation. The manual inventory control is a temporary MVP band-aid that will be revamped when the Inventory module is available.
5. When readiness passes, the Service Order becomes Ready and the system creates one Marine Operation in an awaiting-start state.
6. Every assigned tug has one Tug Master. Each Tug Master records actual start when work begins, then submits actual end, a completion note, and optional evidence when its work finishes.
7. The Marine Operation's overall start and end are derived from the earliest participating tug start and latest participating tug end. A multi-tug Service Order reaches Service Completion only after every active tug assignment has a submitted Tug Completion.
8. Service Completion automatically completes the Marine Operation and sends the order to Billing Review. It does not create an invoice automatically.
9. Finance reviews the customer, Confirmed Rate, actual billable quantity, minimum charge, and Billing Adjustments.
10. Time-based charges use actual time. A per-tug-hour charge is the sum of the actual hours of all completed tug assignments.
11. A missing approved tariff creates a Pricing Exception and blocks invoice creation.
12. Finance creates a draft Odoo customer invoice. Odoo then owns posting, Accounts Receivable, service income, taxes, payment terms, credit notes, and payment processing.
13. Finance records a client payment using the receiving bank journal, date, amount, invoice reference, and optional deposit proof. The Service Order shows the invoice's unpaid, partial or in-payment, and paid status.

## Roles and authority

### Client

- Creates a Service Order and confirms the quoted service.
- Cannot change tariffs, completion records, Billing Reviews, or invoices.

### Marketing or Customer Relations

- Reviews the request and resolves the tariff before client confirmation.
- Cannot approve or rewrite Client Tariffs.

### Tug Master

- Can access only assigned tug work relevant to completion.
- Records actual start, actual end, completion note, and optional evidence.
- Can correct a returned completion and resubmit it.

### Operations User

- Records the temporary Inventory Readiness Confirmation, including automatic confirmer and timestamp audit data.
- Cannot override tugboat or crew readiness checks.
- Does not act as a Dispatcher or Dispatch Manager; the system evaluates the combined readiness gate.

### Billing Officer

- Reviews completed Service Orders.
- Adds explained Billing Adjustments.
- Returns incorrect completion data to the Tug Master with a reason.
- Creates the draft customer invoice from an eligible Billing Review.
- Cannot change approved tariff master data or directly rewrite Tug Completion facts.

### Accounting Manager

- Creates, revises, and approves Client Tariffs after the required business authorization.
- Uses effective-dated tariff versions instead of overwriting approved historical rates.
- Uses standard Odoo Accounting authority for posting invoices and managing accounting records.

## Pricing rules

### Tariff matching

A tariff match requires:

- Client
- Terminal
- Service or move
- Scheduled service date within the tariff's effective period
- Tug class when the tariff restricts it
- Approved status

The current mock data supplies client-specific rates for harbor, towage, berthing, and shifting services. Emergency service deliberately has no tariff and remains a Pricing Exception example.

### Rate freezing

Client confirmation freezes the tariff reference and pricing values on the Service Order. Billing does not perform a live rate lookup that could silently replace the agreed rate.

If the scheduled service date moves into a different tariff period, the order requires Finance review before billing.

### Billable quantity

- Per service: `1`
- Per tug: actual completed tug count
- Per hour: actual Service Order elapsed time, if this basis remains in configured data
- Per tug-hour: sum of each tug assignment's Actual Service Time
- Per day: derived from actual time using the configured tariff rule

The implementation must not use estimated duration for final time-based billing.

### Base charge and minimum charge

The base charge is the tariff calculation using the Confirmed Rate and actual billable quantity. The tariff minimum charge applies when it is greater than the calculated base charge.

### Billing Adjustments

Finance may add a charge or deduction with:

- Description
- Quantity
- Unit rate
- Reason

No fuel, standby, overtime, rebate, or consumable formula will be invented. These remain manual until SEDAR supplies approved rules.

## Completion corrections

- Before invoicing: Finance returns the Tug Completion with a mandatory reason. Only the Tug Master corrects and resubmits it.
- After draft invoice creation: cancel the draft invoice, return and correct the completion, then create a new draft invoice.
- After invoice posting: preserve the accounting record and use Odoo's credit-note and reinvoice process.

Finance must never silently alter a Tug Master's operational record.

## Status model

Operational and billing states remain separate.

### Operational status

The existing Service Order lifecycle continues through planning, ready, dispatched, in progress, and Service Completed.

### Billing status

- Not ready
- Billing Review
- Pricing Exception
- Draft Invoice
- Invoiced
- Partial or In Payment
- Paid
- Cancelled or Credited

An unpaid invoice does not reopen a completed tug operation.

## Odoo module design

### `sedar_marine_operations`

Extend the operational module because Tug Completion is an operational fact, not an accounting record.

Planned changes:

- Extend `sedar.tug.assignment` with the assigned Tug Master, actual start, actual end, completion note, optional evidence, completion state, submission metadata, and return reason.
- Derive or validate the Tug Master from the confirmed crew assignment with rank code `MASTER`.
- Link crew employees to Odoo users so the system can enforce who may declare completion.
- Add actions to submit, return, correct, and resubmit Tug Completions.
- Compute Service Completion only when all active tug assignments are complete.
- Keep estimated and requested time for planning only.
- Add a focused Tug Master work view for assigned services.

### `sedar_marine_finance`

Create a separate addon that depends on `sedar_marine_dispatch` and Odoo `account`.

Planned models and extensions:

- Extend `sedar.client.tariff` with a terminal dimension, approval metadata, effective-dated revision controls, and immutable approved versions.
- Extend `sedar.marine.service.order` with frozen pricing values, Billing Review data, Billing Status, adjustment lines, and linked invoices.
- Add `sedar.marine.billing.adjustment` for explained charges and deductions.
- Extend `account.move` with a Service Order link.
- Calculate base charge, minimum charge, adjustments, and total billable amount without posting journal entries directly.
- Create one draft customer invoice from an eligible Billing Review and prevent accidental duplicate active invoices.
- Read invoice and payment state from Odoo instead of maintaining a second payment ledger.

Planned views:

- Finance Billing Review queue
- Pricing Exception queue
- Billing tab and invoice smart button on Service Orders
- Tariff revision and approval views for Accounting Managers
- Filters for uninvoiced, draft, posted, partial or in-payment, paid, and overdue invoices

### Security

Add explicit groups for:

- Tug Master
- Billing Officer
- Accounting Manager

Server-side methods must enforce the same authority as the interface. Hiding a button is not sufficient security.

## File-level change map

Expected operational changes:

- `sedar-new/custom-addons/sedar_marine_operations/models/marine_crew.py`
- `sedar-new/custom-addons/sedar_marine_operations/models/marine_service_order.py`
- `sedar-new/custom-addons/sedar_marine_operations/views/sedar_marine_views.xml`
- `sedar-new/custom-addons/sedar_marine_operations/security/sedar_marine_security.xml`
- `sedar-new/custom-addons/sedar_marine_operations/security/ir.model.access.csv`

Expected new Finance addon:

- `sedar-new/custom-addons/sedar_marine_finance/__init__.py`
- `sedar-new/custom-addons/sedar_marine_finance/__manifest__.py`
- `sedar-new/custom-addons/sedar_marine_finance/models/__init__.py`
- `sedar-new/custom-addons/sedar_marine_finance/models/marine_finance.py`
- `sedar-new/custom-addons/sedar_marine_finance/models/account_move.py`
- `sedar-new/custom-addons/sedar_marine_finance/security/sedar_marine_finance_security.xml`
- `sedar-new/custom-addons/sedar_marine_finance/security/ir.model.access.csv`
- `sedar-new/custom-addons/sedar_marine_finance/views/sedar_marine_finance_views.xml`
- `sedar-new/custom-addons/sedar_marine_finance/data/sedar_marine_finance_data.xml`
- `sedar-new/custom-addons/sedar_marine_finance/tests/`

Expected mock-data changes:

- `sedar-new/custom-addons/sedar_service_order_demo/hooks.py`
- `sedar-new/custom-addons/sedar_service_order_demo/__manifest__.py`

## Validation scenarios

The implementation is not complete until these scenarios pass:

1. A single-tug job cannot enter Billing Review before its Tug Master submits completion.
2. A two-tug job remains operationally incomplete after only one Tug Master submits.
3. A two-tug per-tug-hour job bills the sum of both actual durations.
4. Estimated duration never changes the final time-based amount after actual times exist.
5. A Billing Officer cannot edit or approve a Client Tariff.
6. An Accounting Manager can approve a new effective-dated tariff version without changing the old version.
7. Missing terminal or tariff coverage creates a Pricing Exception and blocks invoice creation.
8. A returned completion requires a reason and can be corrected only by the assigned Tug Master.
9. Billing Adjustments require a description and reason and appear as separate invoice lines.
10. An eligible Billing Review creates one draft customer invoice linked to the Service Order.
11. A second active invoice cannot be created accidentally for the same Billing Review.
12. Posting and registering a partial or full payment in Odoo updates the Service Order's Billing Status.
13. Cancelling a draft invoice permits correction and controlled regeneration.
14. A posted invoice correction uses a credit note instead of rewriting accounting history.

## Demo script

1. Open a confirmed two-tug Service Order with an approved mock tariff.
2. Show that both tug and crew plans are ready.
3. Sign in as the first Tug Master and submit actual time and completion notes.
4. Show that the Service Order is not yet complete.
5. Sign in as the second Tug Master and submit completion.
6. Open the Finance Billing Review queue and show the newly eligible order.
7. Review the frozen tariff, summed tug-hours, minimum charge, and one explained adjustment.
8. Create the draft Odoo customer invoice.
9. Post the invoice and show the Accounts Receivable and service-income result in Odoo.
10. Register a client bank payment and show the Service Order's Billing Status change to paid.

## Explicit assumptions requiring later confirmation

- One Service Order represents one billable tug assist or move at one terminal.
- Multi-tug services normally operate in tandem, but the system records actual time per tug.
- The Tug Master has final authority to declare their assigned tug's work complete.
- The scheduled service date selects the tariff, and client confirmation freezes the rate.
- Manual Billing Adjustments are allowed, but automatic surcharge and rebate formulas are not yet known.
- Full bank reconciliation and broader finance automation are deferred.

## Out of scope for this MVP

- Custom general ledger
- Petty cash and cash advances
- Expense encoding and liquidation
- Purchase-order, check-voucher, and disbursement matching
- Supplier-payment tracking
- Agent rebates or commissions
- Custom taxes or Philippine electronic-invoicing rules
- Bank-statement reconciliation and bounced-check handling
- Daily cash-flow reporting
- Full financial statements and executive expense reporting

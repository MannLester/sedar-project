# Build Service Order billing on Odoo Accounting

SEDAR's custom modules will own Service Completion, Client Tariff selection, Billing Review, Billing Adjustments, and the handoff from a Service Order to a draft customer invoice. Standard Odoo Accounting will own invoice posting, Accounts Receivable, service income entries, taxes, payment terms, payments, reconciliation, credit notes, and accounting reports. This avoids creating a second ledger while still giving the demo a complete job-to-payment story.

## Status

Accepted

## Considered options

- Build a custom finance ledger. Rejected because it would duplicate Odoo, increase accounting risk, and exceed the evidence available from SEDAR.
- Implement the finance department's full requested scope now. Deferred because petty cash, disbursements, purchase-order matching, rebates, bank reconciliation, and cash-flow reporting require more process details.

## Consequences

- The custom Finance module depends on Odoo Accounting.
- A Service Order creates only a draft customer invoice after Billing Review. It does not post journal entries directly.
- Payment and invoice truth come from Odoo accounting records, while the Service Order exposes the related billing status.
- The MVP can expand into the deferred finance workflows without replacing its invoice or ledger foundation.

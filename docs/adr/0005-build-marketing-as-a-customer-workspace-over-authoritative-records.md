# Build Marketing as a customer workspace over authoritative records

The Marketing application will provide the customer-centred workflow and presentation from the approved SEDAR layout without creating another operational or accounting truth. `res.partner` owns customer and contact identity, `sedar.marine.service.order` remains the Service Request/Job Order, Odoo Accounting remains authoritative for invoices and payments, and official `sedar.document` records remain owned by their source departments. Marketing owns its quotations, contracts, appointments, internal notes, metadata-only customer document register, sanitized append-only activity trail, and read-only cross-department transaction projection. This keeps the reference workflow usable while preserving the boundaries in ADR-0001 through ADR-0004.

## Status

Accepted

## Consequences

- Marketing may display and filter operational, accounting, and official document facts, but cannot rewrite them through its customer workspace.
- Marketing-owned document entries store metadata and version facts only; official controlled files remain in Document Control.
- A Marketing quotation records a commercial offer and approval history but does not create, post, or reconcile an invoice.
- A Marketing contract records terms and signatures but does not replace the effective-dated Client Tariff or the Service Order's frozen pricing and billing controls.

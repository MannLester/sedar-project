# Architecture Decision Records

Accepted ADRs are repository constraints. Read the ones that relate to a task before changing
behavior. Do not edit an accepted decision; add the next numbered ADR and mark what it supersedes.

| ADR | Decision | Read when working on |
| --- | --- | --- |
| [0001](0001-build-service-order-billing-on-odoo-accounting.md) | Billing handoff is SEDAR's; the ledger is Odoo Accounting's | Finance, invoicing, billing status |
| [0002](0002-automate-readiness-and-completion-handoff.md) | Readiness, Marine Operation creation, and completion are automated | Service Order lifecycle, dispatch, completion |
| [0003](0003-separate-headcount-fulfillment-from-operational-shortage-resolution.md) | Headcount fulfillment is separate from shortage resolution | Manpower, recruitment, crew shortages |
| [0004](0004-use-odoo-stock-movements-for-authoritative-inventory.md) | Odoo stock moves are the inventory truth | Inventory, procurement receipts, fuel, parts |
| [0005](0005-build-marketing-as-a-customer-workspace-over-authoritative-records.md) | Marketing is a customer workspace over authoritative records | Marketing, customer portal |
| [0006](0006-model-ais-as-an-explicit-simulated-feed.md) | AIS is an explicit simulated feed | Fleet map |
| [0007](0007-award-procurement-bids-per-purchase-request-line.md) | Bids are awarded per Purchase Request line | Procurement |
| [0008](0008-track-tugboat-inventory-until-removal-or-consumption.md) | Tugboat inventory is tracked until removal or consumption | Inventory lifecycle |
| [0009](0009-own-service-order-aggregates-by-company.md) | Service Orders are owned by exactly one company | Multi-company access, record rules |
| [0010](0010-separate-technical-removal-from-inventory-disposition.md) | Technical Removal is separate from Inventory Disposition | Equipment, inventory disposition |
| [0011](0011-enforce-deep-addon-boundaries.md) | Addons are deep modules with declared public surfaces | Any cross-addon change, new addons, new checks |

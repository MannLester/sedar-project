# Award procurement bids per Purchase Request line

SEDAR Procurement will own supplier Bid capture, comparison, and Line Awards before handing awarded goods to standard Odoo Purchase. A Bidder may quote any subset of a Purchase Request; the Procurement and Inventory Officer selects one Bidder for the full quantity of each line with a mandatory justification, then the system groups awarded lines by winning supplier and creates one standard Odoo Purchase Order per supplier. This replaces the current preferred-vendor, single-RFQ handoff because SEDAR commonly receives incomplete supplier quotations, while preserving Odoo Purchase, Inventory, and Accounting as the owners of orders, receipts, supplier bills, and ledger entries.

## Status

Accepted

## Consequences

- One Purchase Request may produce multiple Purchase Orders.
- A line quantity cannot be split between Bidders; Procurement must split the request line before award when separate suppliers are required.
- Price, delivery, availability, warranty, and payment terms inform a manual best-value decision; the lowest price does not win automatically.
- Losing and unawarded Bids remain as procurement history.
- The Procurement and Inventory Officer performs request approval, Bid entry, Line Awards, and Purchase Order creation for the current company workflow; there is no separate Purchase Request Manager business role.
- Supplier portal submission, external services, automatic bid scoring, and automatic procurement from Running Hours are outside this scope.

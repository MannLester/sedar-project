# Use Odoo stock movements for authoritative inventory

## Status

Accepted

## Context

SEDAR inventory readiness is now derived from Odoo stock quantities, but the first demonstration implementation changed `stock.quant` directly. That makes readiness appear to work while losing standard receipt, issue, transfer, return, and valuation traceability.

## Decision

Standard Odoo Inventory is the authoritative transaction record for SEDAR stock. SEDAR inventory requirements, maintenance parts, and fuel logs may keep domain-specific quantities and source links, but issue, receipt, transfer, return, and consumption actions must create and validate standard Odoo stock moves or pickings. Direct quant mutation is reserved for controlled fixture initialization only.

## Relationship to earlier decisions

This decision supersedes the temporary manual-inventory wording in ADR-0002. The remaining ADR-0002 boundary is preserved: Inventory owns stock truth and SEDAR owns the Dispatch Readiness Gate that consumes it.

## Consequences

- Inventory actions have auditable Odoo movement history.
- Procurement receipts replenish the same quantities used by readiness.
- SEDAR retains links from domain lines to stock moves or pickings.
- Demo fixtures may initialize stock quantities once, but user-facing workflows cannot bypass Odoo Inventory transactions.

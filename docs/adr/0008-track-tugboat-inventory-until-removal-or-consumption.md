# Track tugboat inventory until removal or consumption

An Inventory Issue will move physical goods from warehouse Storage to a named tugboat through standard Odoo stock movements instead of treating issue as immediate consumption. Goods assigned to or installed on the tugboat remain visible as Currently In Use, with the related tugboat and Equipment when applicable, until an explicit removal or consumption records the next stock movement. This supersedes the initial one-step-consumption MVP behavior while preserving ADR-0004: standard Odoo stock moves and locations remain authoritative for quantity and movement truth.

## Status

Superseded in part by ADR-0010, which distinguishes technical Equipment removal from physical Inventory Disposition.

## Consequences

- Warehouse Storage, tugboat-held stock, installed goods, removal, and consumption remain traceable as separate facts.
- The existing tugboat stock locations become operational destinations rather than unused reference data.
- Replacement Equipment becomes individually tracked Equipment only when installation is recorded.
- Historical one-step Inventory Issues and their completed stock movements remain unchanged during migration; new lifecycle records begin with new issues.
- Returns, removals, and consumption cannot directly mutate stock quantities and must use controlled Odoo stock movements.

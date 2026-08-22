# Separate technical removal from Inventory Disposition

Technical Removal records that Replacement Equipment was uninstalled while the physical unit remains at the tugboat's stock location; a later return, consumption, or disposal records the Inventory Disposition and its controlled Odoo stock movement. This preserves Equipment identity and Running Hour history, lets Maintenance hand the disposition decision to the Procurement and Inventory Officer, and supersedes ADR-0008 only where its use of “removal” implied that technical uninstall and physical stock removal were the same event.

## Status

Accepted

## Consequences

- Technical Removal clears the Equipment's active tugboat installation context, keeps the Inventory Lifecycle open, and schedules one disposition activity for the configured Procurement and Inventory Officer.
- Goods awaiting disposition remain visible in Currently In Use with a removed/pending-disposition status because Odoo still locates them at the tugboat.
- Return, consumption, and disposal remain the only physical closing actions; each uses a controlled Odoo stock movement and reduces the open lifecycle quantity.

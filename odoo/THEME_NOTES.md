# SEDAR MVP Theme Notes

Reference image:

```text
resources/bb072332-4bf0-49da-81db-f72dcd9a4095.jpg
```

## What We Borrowed

The reference is used only for visual direction:

- Deep maritime navy base.
- White/ice text and icon contrast.
- Soft blue accent for active states.
- Thin divider lines.
- Compact business-application feel.
- Simple placeholder logo/wordmark treatment.

## What We Did Not Copy

We did not copy the exact sidebar, logo, icon arrangement, user profile block, or menu list.

The actual Odoo menu structure remains based on `resources/Web System.pdf`:

- Dashboard.
- Marine Operations.
- Fleet Management.
- Technical Maintenance.
- Crewing.
- Human Resources.
- HSSE.
- Finance.
- Procurement.
- Inventory.
- Document Control.
- Management Reports.

## Current Implementation

The Odoo backend theme is implemented in:

```text
custom_addons/sedar_marine_mvp/static/src/css/sedar_backend_theme.css
```

This is a lightweight Odoo Community-compatible theme layer. It improves the backend navigation, menu, kanban, list, and action styling without replacing the Odoo web client.


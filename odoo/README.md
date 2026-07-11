# SEDAR Odoo Community MVP

This folder contains Odoo Community support files and the retired first prototype. The supported SEDAR MVP runs on Odoo 17 from the repository root.

## Why Start Here

The current Community Edition prototype uses:

- Odoo 17 Community.
- Modular project-owned addons under `../addons/`.
- Sample/demo data only.
- Dashboard-first menus split into separate Odoo app areas.
- Coverage for every module requested in `resources/Web System.pdf`.

## Run With Docker

From the repository root:

```powershell
docker compose up -d
```

Then open:

```text
http://localhost:8069
```

Follow the root [README](../README.md) to create the database and install the current SEDAR modules. Do not install `custom_addons/sedar_marine_mvp`; it is retained only for legacy data review.

The installed MVP now exposes these top-level app areas:

- SEDAR Dashboard.
- Marine Operations.
- Finance.
- Fleet Management.
- Crewing.
- HSSE.
- Procurement.
- Inventory.
- Human Resources.
- Document Control.
- Management Reports.

## Where Are The Community Files?

The Odoo Community source and built-in Community apps come from the Docker image. They are not copied into this repository. See [community/README.md](community/README.md).

## Theme Direction

The backend theme borrows only the palette and design mood from the sidebar reference image in `resources/`. It does not copy the exact layout. See [THEME_NOTES.md](THEME_NOTES.md).

## Community Edition Boundary

The MVP uses custom lightweight models so we can show all requested business areas in Odoo Community:

- Finance and Accounting.
- Tug Operations.
- Technical and Maintenance.
- HSE.
- Crewing.
- Procurement.
- Inventory.
- HR.
- Document Control.
- Management Dashboard.

Full production accounting, payroll, bank reconciliation, AIS/GPS integration, barcode scanning, digital signatures, and Power BI embedding remain later implementation items.

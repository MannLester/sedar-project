# SEDAR Odoo Community MVP

This is the Odoo Community starting point for the SEDAR tug ERP and marine fleet management MVP.

## Why Start Here

Step 1 is the dashboard and module map. This Odoo project turns that map into a runnable Community Edition prototype:

- One custom addon: `sedar_marine_mvp`.
- Sample/demo data only.
- Dashboard-first menus split into separate Odoo app areas.
- Coverage for every module requested in `resources/Web System.pdf`.

## Run With Docker

From this folder:

```powershell
docker compose up -d
```

Then open:

```text
http://localhost:8069
```

Create a database and install the `SEDAR Marine MVP` app.

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

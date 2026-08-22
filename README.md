# SEDAR Tug Services ERP / Marine Fleet Demonstration

This repository contains the active SEDAR Odoo 19 demonstration and its supporting business and
architecture documentation. The working implementation is in [`sedar-new/`](sedar-new/); the
older [`odoo/`](odoo/) tree is retained only as legacy reference.

The demonstration connects Service Orders, tug and crew dispatch, maintenance, procurement,
inventory, HSSE, recruitment, billing, accounting, and management reporting in one Odoo database.
All seeded companies, people, rates, positions, quotations, and transactions are fictional. This
is not a production deployment or a claim of live AIS/GPS, regulatory, tax, payroll, or security
certification.

## Requirements

- Docker Desktop
- Git
- A modern browser

Local Python is needed only for the optional developer-quality checks.

## Start the active workspace

```sh
git clone https://github.com/MannLester/sedar-project.git
cd sedar-project/sedar-new
docker compose up -d
```

The Compose startup installs and upgrades the complete module list into `sedar_demo`. Open:

```text
http://localhost:8069/web?db=sedar_demo
```

See [`sedar-new/README.md`](sedar-new/README.md) for demo accounts, workflows, local quality
checks, and focused Odoo test commands.

## Procurement demonstration

The Procurement workspace supports physical Inventory Items, tugboat spare parts, and Replacement
Equipment. A Procurement and Inventory Officer records partial supplier Bids, awards each requested
product to one Bidder with a reason, and creates one standard Odoo Purchase Order per winning
supplier. Standard Odoo Inventory owns receipts and stock movements. Issued goods move from
warehouse Storage to a tugboat and remain visible as Currently In Use until a controlled return,
consumption, or disposal.

The simulated fleet map shows installed Equipment and cumulative Running Hours. Selecting Equipment
opens its active procurement and order history; protected Bid prices, terms, suppliers, and
quotation attachments are returned only to the configured Procurement and Inventory Officer.

## Documentation

- [`CONTEXT.md`](CONTEXT.md): canonical business terms
- [`docs/project-requirements.md`](docs/project-requirements.md): demonstration requirements
- [`docs/implementation-status.md`](docs/implementation-status.md): shipped capability status
- [`docs/custom-models.md`](docs/custom-models.md): custom Odoo model and workflow contract
- [`docs/adr/`](docs/adr/): accepted architecture decisions
- [`docs/procurement-module-implementation-plan.md`](docs/procurement-module-implementation-plan.md): approved Procurement scope and verification contract

## Resetting local data

Stop the stack without deleting its database:

```sh
cd sedar-new
docker compose down
```

For a fresh environment, stop Compose and move `data/postgres` and `data/odoo` to a named backup
outside the workspace before restarting. Those directories contain the local Odoo database and
filestore and cannot be recovered from Git. Confirm the exact paths and backup before removing
anything; do not reset an environment whose data must be retained.

# Odoo Community Source Boundary

This folder contains pinned OCA repositories used to extend Odoo Community without editing upstream modules.

The Odoo Community code and standard Community apps are provided by the Docker image:

```text
odoo:17.0
```

Inside the running container, Odoo's standard addons live at:

```text
/usr/lib/python3/dist-packages/odoo/addons
```

We do not copy the full Odoo Community source tree into this repository because it is large and not needed. Project-owned addons live in:

```text
../addons/
```

The legacy MVP addon lives in:

```text
custom_addons/sedar_marine_mvp
```

Pinned OCA 17 repositories:

- `account-financial-reporting` provides General Ledger, Trial Balance, Open Items, Aged Partner Balance, VAT, and Journal Ledger reports.
- `server-ux` provides the required `date_range` module.
- `reporting-engine` provides the required XLSX report engine.

The architecture is:

- Docker image provides Odoo Community.
- Pinned OCA submodules provide selected Community extensions.
- `../addons` provides current SEDAR-specific features.
- `custom_addons` contains the legacy MVP addon.
- `config` provides local Odoo configuration.

# Odoo Community Source Boundary

This folder is intentionally documentation-only for now.

The Odoo Community code and standard Community apps are provided by the Docker image:

```text
odoo:19.0
```

Inside the running container, Odoo's standard addons live at:

```text
/usr/lib/python3/dist-packages/odoo/addons
```

We do not copy the full Odoo Community source tree into this repository because it is large, noisy, and not necessary for an MVP. The project-owned code belongs in:

```text
custom_addons/
```

Current project addon:

```text
custom_addons/sedar_marine_mvp
```

If we later need to modify or vendor specific Community modules, we can add them here deliberately. For now, the cleaner architecture is:

- Docker image provides Odoo Community.
- `custom_addons` provides SEDAR-specific MVP features.
- `config` provides local Odoo configuration.


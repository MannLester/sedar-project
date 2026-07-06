# Seed Data

Run after all modules are installed:

```powershell
docker compose exec -T odoo odoo shell -d sedar < scripts/seed_data.py
```

Safe to re-run. It exits early if vessels already exist.

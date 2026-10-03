from odoo import SUPERUSER_ID, api


def _location(env, company, role, parent, tugboat=None):
    domain = [
        ("company_id", "=", company.id),
        ("sedar_location_role", "=", role),
    ]
    if tugboat:
        domain.append(("sedar_tugboat_id", "=", tugboat.id))
    else:
        domain.append(("sedar_tugboat_id", "=", False))
    location = env["stock.location"].search(domain, limit=1)
    values = {
        "usage": "internal",
        "location_id": parent.id,
        "company_id": company.id,
        "sedar_location_role": role,
        "sedar_tugboat_id": tugboat.id if tugboat else False,
    }
    if location:
        location.write(values)
        return location
    values["name"] = (
        "%s Quarantine" % tugboat.display_name
        if tugboat
        else "SEDAR Storage Quarantine"
    )
    return env["stock.location"].create(values)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env["res.company"].with_context(active_test=False).search([]):
        storage = company.sedar_default_storage_location_id
        if storage:
            quarantine = _location(
                env, company, "storage_quarantine", storage
            )
            company.sedar_quarantine_location_id = quarantine
        tugboats = env["sedar.tugboat"].with_context(active_test=False).search([
            ("company_id", "=", company.id),
            ("stock_location_id", "!=", False),
        ])
        for tugboat in tugboats:
            quarantine = _location(
                env,
                company,
                "tug_quarantine",
                tugboat.stock_location_id,
                tugboat,
            )
            tugboat.quarantine_location_id = quarantine
        virtual_parent = env["stock.location"].search([
            ("usage", "=", "view"),
            ("company_id", "in", [False, company.id]),
        ], order="company_id desc, id", limit=1)
        adjustment = env["stock.location"].search([
            ("company_id", "=", company.id),
            ("sedar_location_role", "=", "adjustment"),
        ], limit=1)
        values = {
            "name": "SEDAR Inventory Adjustment",
            "usage": "inventory",
            "location_id": virtual_parent.id,
            "company_id": company.id,
            "sedar_location_role": "adjustment",
        }
        if adjustment:
            adjustment.write(values)
        else:
            adjustment = env["stock.location"].create(values)
        company.sedar_adjustment_location_id = adjustment
    env["sedar.replenishment.demand"]._sync_inventory_shortages()

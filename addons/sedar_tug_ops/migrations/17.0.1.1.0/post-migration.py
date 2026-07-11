from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Vessel = env['sedar.vessel']
    target_names = [f'M/TUG SEDAR {number}' for number in range(1, 10)]

    existing_targets = Vessel.search([('name', 'in', target_names)])
    assigned_names = set(existing_targets.mapped('name'))
    legacy_vessels = Vessel.search(
        [('name', 'not in', target_names)],
        order='name, id',
        limit=len(target_names) - len(assigned_names),
    )

    for vessel in legacy_vessels:
        available_name = next(name for name in target_names if name not in assigned_names)
        vessel.name = available_name
        assigned_names.add(available_name)

    for name in target_names:
        if name not in assigned_names:
            Vessel.create({'name': name})

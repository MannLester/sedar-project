{
    "name": "SEDAR Marine Maintenance",
    "version": "19.0.2.0.0",
    "category": "Marine",
    "summary": "Marine maintenance, defects, dry dock planning, and tug availability controls",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["maintenance", "sedar_marine_operations", "sedar_marine_dispatch"],
    "data": [
        "security/sedar_marine_maintenance_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marine_maintenance_activity_data.xml",
        "views/sedar_marine_maintenance_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

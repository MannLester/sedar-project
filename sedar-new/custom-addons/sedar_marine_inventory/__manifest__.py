{
    "name": "SEDAR Marine Inventory",
    "version": "19.0.2.0.0",
    "category": "Marine",
    "summary": "Marine inventory readiness, spare parts, fuel, and lubricant controls",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "sedar_marine_dispatch",
        "sedar_marine_maintenance",
        "sedar_marine_dispatch_demo",
    ],
    "data": [
        "security/sedar_marine_inventory_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_inventory_sequence.xml",
        "views/sedar_marine_inventory_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

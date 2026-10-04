{
    "name": "SEDAR Marine Maintenance",
    "version": "19.0.5.0.0",
    "category": "Marine",
    "summary": "Marine maintenance, planned maintenance by running hours, daily engine reports, defects, dry dock planning, and tug availability controls",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["maintenance", "sedar_marine_operations", "sedar_marine_dispatch"],
    "data": [
        "security/sedar_marine_maintenance_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marine_maintenance_activity_data.xml",
        "views/sedar_marine_maintenance_views.xml",
        "views/sedar_pm_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_marine_maintenance/static/src/js/engine_room_action.js",
            "sedar_marine_maintenance/static/src/xml/engine_room_action.xml",
            "sedar_marine_maintenance/static/src/css/engine_room_action.css",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

{
    "name": "SEDAR Simulated AIS Fleet Monitoring",
    "version": "19.0.2.0.0",
    "category": "Marine",
    "summary": "Offline-safe simulated AIS/GPS fleet map for client demonstrations",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "web",
        "sedar_marine_dispatch_demo",
        "sedar_marine_maintenance",
        "sedar_crew_scheduling",
        "sedar_purchase_request",
    ],
    "data": [
        "security/sedar_ais_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_ais_bootstrap.xml",
        "views/sedar_ais_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_ais_demo/static/src/js/ais_dashboard.js",
            "sedar_ais_demo/static/src/xml/ais_dashboard.xml",
            "sedar_ais_demo/static/src/css/ais_dashboard.css",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}

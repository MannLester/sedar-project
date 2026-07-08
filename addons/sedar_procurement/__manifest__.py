{
    "name": "SEDAR Procurement",
    "summary": "Procurement dashboard, requests, purchase orders, and reorder signals",
    "version": "19.0.1.0.0",
    "category": "Operations/Purchase",
    "author": "Mann, Edrian, and Clarenz",
    "license": "LGPL-3",
    "depends": ["base", "web", "sedar_marine_mvp"],
    "data": [
        "security/ir.model.access.csv",
        "views/procurement_views.xml",
        "data/procurement_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_procurement/static/src/xml/procurement_dashboard.xml",
            "sedar_procurement/static/src/js/procurement_dashboard.js",
            "sedar_procurement/static/src/css/procurement_dashboard.css",
        ],
    },
    "application": True,
    "installable": True,
}

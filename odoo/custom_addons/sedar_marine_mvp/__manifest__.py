{
    "name": "SEDAR Marine MVP",
    "summary": "Dashboard-first tug ERP and marine fleet management MVP for Odoo Community",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "author": "Mann, Edrian, and Clarenz",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/sedar_marine_views.xml",
        "demo/sedar_marine_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_marine_mvp/static/src/xml/sedar_sidebar.xml",
            "sedar_marine_mvp/static/src/xml/document_risk_dashboard.xml",
            "sedar_marine_mvp/static/src/js/document_risk_dashboard.js",
            "sedar_marine_mvp/static/src/css/sedar_backend_theme.css",
        ],
    },
    "application": True,
    "installable": True,
}

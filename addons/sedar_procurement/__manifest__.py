{
    "name": "SEDAR Procurement",
    "summary": "SEDAR procurement UI backed by native Purchase and Inventory",
    "version": "19.0.1.0.0",
    "category": "Operations/Purchase",
    "author": "Mann, Edrian, and Clarenz",
    "license": "LGPL-3",
    "depends": ["base", "web", "purchase", "stock", "sedar_marine_mvp"],
    "data": [
        "security/ir.model.access.csv",
        "data/company_config.xml",
        "data/currency_config.xml",
        "views/procurement_views.xml",
        "reports/canvas_sheet_report.xml",
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

{
    "name": "SEDAR Procurement",
    "summary": "SEDAR procurement UI backed by native Purchase and Inventory",
    "version": "17.0.1.1.0",
    "category": "Operations/Purchase",
    "author": "Mann, Edrian, and Clarenz",
    "license": "LGPL-3",
    "depends": ["base", "web", "purchase", "stock", "maintenance", "sedar_tug_ops"],
    "data": [
        "security/ir.model.access.csv",
        "data/company_config.xml",
        "data/currency_config.xml",
        "views/procurement_views.xml",
        "reports/canvas_sheet_report.xml",
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

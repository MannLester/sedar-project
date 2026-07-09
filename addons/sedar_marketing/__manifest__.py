{
    "name": "SEDAR Marketing Customer Support",
    "summary": "Customer support intake flow for Marketing",
    "version": "17.0.1.0.0",
    "category": "Sales/CRM",
    "author": "Mann, Edrian, and Clarenz",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "sedar_marine_mvp"],
    "data": [
        "security/ir.model.access.csv",
        "views/marketing_views.xml",
        "views/menu.xml",
        "data/marketing_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_marketing/static/src/xml/marketing_dashboard.xml",
            "sedar_marketing/static/src/js/marketing_dashboard.js",
            "sedar_marketing/static/src/css/marketing.css",
        ],
    },
    "application": True,
    "installable": True,
}

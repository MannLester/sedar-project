{
    "name": "SEDAR Marine Finance",
    "version": "19.0.3.0.0",
    "category": "Accounting/Accounting",
    "summary": "Billing review and Odoo invoicing for completed marine services",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_marine_operations", "sedar_marine_dispatch", "account", "web"],
    "data": [
        "security/sedar_marine_finance_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marine_finance_data.xml",
        "views/sedar_marine_finance_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_marine_finance/static/src/js/finance_dashboard.js",
            "sedar_marine_finance/static/src/xml/finance_dashboard.xml",
            "sedar_marine_finance/static/src/css/finance_dashboard.css",
        ],
    },
    "installable": True,
    "application": False,
}

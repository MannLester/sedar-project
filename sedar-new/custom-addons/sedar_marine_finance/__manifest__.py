{
    "name": "SEDAR Marine Finance",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Billing review and Odoo invoicing for completed marine services",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_marine_operations", "sedar_marine_dispatch", "account"],
    "data": [
        "security/sedar_marine_finance_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marine_finance_data.xml",
        "views/sedar_marine_finance_views.xml",
    ],
    "installable": True,
    "application": False,
}

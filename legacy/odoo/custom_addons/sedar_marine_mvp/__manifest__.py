{
    "name": "SEDAR Marine MVP",
    "summary": "Dashboard-first tug ERP and marine fleet management MVP for Odoo Community",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "author": "Mann, Edrian, and Clarenz",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/sedar_marine_views.xml",
        "demo/sedar_marine_demo.xml",
    ],
    "application": True,
    "installable": True,
}

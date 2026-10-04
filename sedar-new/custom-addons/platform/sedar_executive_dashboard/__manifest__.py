{
    "name": "SEDAR Corporate Governance and Executive Dashboard",
    "version": "19.0.3.0.0",
    "category": "Operations",
    "summary": "Corporate document registers and source-backed executive KPIs",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_document_control", "sedar_hsse", "sedar_purchase_request",
        "sedar_marine_finance", "sedar_marine_inventory", "sedar_marine_maintenance",
        "sedar_crew_compliance",
        "sedar_manpower_planning", "account", "mail",
    ],
    "data": [
        "security/sedar_executive_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_executive_demo.xml",
        "views/sedar_executive_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_executive_dashboard/static/src/scss/executive_dashboard.scss",
        ],
    },
    "installable": True,
    "application": False,
}

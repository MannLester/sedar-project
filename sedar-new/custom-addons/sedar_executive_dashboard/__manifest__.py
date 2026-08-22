{
    "name": "SEDAR Corporate Governance and Executive Dashboard",
    "version": "19.0.2.0.0",
    "category": "Operations",
    "summary": "Corporate document registers and source-backed executive KPIs",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_document_control", "sedar_erp_demo", "sedar_hsse", "sedar_purchase_request",
        "sedar_marine_inventory", "sedar_marine_maintenance", "sedar_crew_compliance",
        "sedar_manpower_planning", "account", "mail",
    ],
    "data": [
        "security/sedar_executive_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_executive_demo.xml",
        "views/sedar_executive_views.xml",
    ],
    "installable": True,
    "application": False,
}

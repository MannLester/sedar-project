{
    "name": "SEDAR Marine Dispatch",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "Dispatch and execution tracking for marine service orders",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_marine_operations", "mail", "portal", "website"],
    "data": [
        "security/sedar_marine_dispatch_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marine_dispatch_sequence.xml",
        "views/sedar_marine_dispatch_views.xml",
        "views/sedar_marine_dispatch_portal_templates.xml",
    ],
    "installable": True,
    "application": True,
}

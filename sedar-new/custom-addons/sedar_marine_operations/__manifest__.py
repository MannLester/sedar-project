{
    "name": "SEDAR Marine Operations",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "Client service-order intake, tariffs, and marine operations planning",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_document_control", "mail", "portal", "website"],
    "data": [
        "security/sedar_marine_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marine_sequence.xml",
        "data/sedar_marine_demo_data.xml",
        "views/sedar_marine_views.xml",
        "views/sedar_marine_portal_templates.xml",
    ],
    "installable": True,
    "application": True,
}

{
    "name": "SEDAR Portal Theme",
    "version": "19.0.1.0.6",
    "category": "Theme/Frontend",
    "summary": "Shared SEDAR visual language for client and applicant portals",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_theme",
        "sedar_marketing",
        "portal",
        "website",
        "sedar_marine_operations",
        "sedar_applicant_intake",
        "sedar_applicant_portal",
    ],
    "assets": {
        "web.assets_frontend": [
            "sedar_portal_theme/static/src/css/sedar_portal.css",
        ],
    },
    "data": [
        "views/sedar_portal_theme_templates.xml",
    ],
    "installable": True,
    "application": False,
}

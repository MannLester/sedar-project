{
    "name": "SEDAR Applicant Portal",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Authenticated applicant dashboard and secure application tracking",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_applicant_intake", "portal", "auth_signup", "website", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/sedar_applicant_portal_data.xml",
        "views/sedar_applicant_portal_views.xml",
        "views/sedar_applicant_portal_templates.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

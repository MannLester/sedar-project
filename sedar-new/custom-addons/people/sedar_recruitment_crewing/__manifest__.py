{
    "name": "SEDAR Recruitment Crewing Handoff",
    "version": "19.0.1.0.0",
    "category": "Marine",
    "summary": "Creates controlled marine crew onboarding after applicant-to-employee conversion",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_recruitment_operations",
        "sedar_manpower_planning",
        "sedar_marine_operations",
    ],
    "data": [
        "security/sedar_recruitment_crewing_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_crew_onboarding_sequence.xml",
        "data/sedar_crew_onboarding_demo.xml",
        "views/sedar_crew_onboarding_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

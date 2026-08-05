{
    "name": "SEDAR Crew Compliance",
    "version": "19.0.1.0.0",
    "category": "Marine",
    "summary": "Controls crew credential and medical evidence, renewal, and readiness impact",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_document_control",
        "sedar_marine_operations",
        "sedar_recruitment_crewing",
    ],
    "data": [
        "security/sedar_crew_compliance_security.xml",
        "data/sedar_crew_compliance_documents.xml",
        "views/sedar_crew_compliance_views.xml",
    ],
    "installable": True,
    "application": False,
}

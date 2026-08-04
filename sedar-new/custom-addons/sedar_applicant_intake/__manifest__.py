{
    "name": "SEDAR Applicant Intake",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Public ADM-3 applicant intake and initial document submission",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_careers", "sedar_document_control", "hr_recruitment", "website", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/sedar_applicant_sequence.xml",
        "views/sedar_applicant_views.xml",
        "views/sedar_applicant_templates.xml",
    ],
    "installable": True,
    "application": False,
}

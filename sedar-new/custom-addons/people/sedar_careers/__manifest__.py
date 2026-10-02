{
    "name": "SEDAR Careers Integration",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Publish approved SEDAR vacancies to the public Careers website",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_manpower_planning", "hr", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/sedar_careers_views.xml",
    ],
    "installable": True,
    "application": False,
}

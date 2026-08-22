{
    "name": "SEDAR Manpower Planning",
    "version": "19.0.2.0.0",
    "category": "Human Resources",
    "summary": "Review marine crew shortages and approve manpower demand",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_marine_dispatch", "hr", "mail"],
    "data": [
        "security/sedar_manpower_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_manpower_sequence.xml",
        "views/sedar_manpower_views.xml",
    ],
    "installable": True,
    "application": True,
}

{
    "name": "SEDAR Crewing Availability",
    "version": "19.0.2.0.0",
    "category": "Marine",
    "summary": "Tracks dated crew unavailability, leave, training blockers, and temporary relief",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "hr_holidays",
        "sedar_crew_compliance",
        "sedar_manpower_planning",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sedar_crewing_availability_views.xml",
    ],
    "installable": True,
    "application": False,
}

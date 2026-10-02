{
    "name": "SEDAR Crew Scheduling",
    "version": "19.0.1.0.0",
    "category": "Marine",
    "summary": "Adds crew rotation planning, assignment confirmation controls, and scheduling views",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_marine_dispatch",
        "sedar_crewing_availability",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sedar_crew_scheduling_views.xml",
    ],
    "installable": True,
    "application": False,
}

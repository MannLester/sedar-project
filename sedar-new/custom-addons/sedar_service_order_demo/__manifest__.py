{
    "name": "SEDAR Service Order Demo Data",
    "version": "19.0.2.0.0",
    "category": "Operations",
    "summary": "Fictional service orders, tugboats, crew, and readiness scenarios",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": ["sedar_marine_operations", "sedar_marine_finance"],
    "data": ["data/demo_company.xml"],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

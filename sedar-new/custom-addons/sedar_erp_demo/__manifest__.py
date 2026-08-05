{
    "name": "SEDAR Broader ERP Demonstration",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "Demonstration-only HR, Finance, and CRM extensions using shared Odoo records",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "hr_attendance", "hr_holidays", "crm", "account", "sedar_marine_finance",
        "sedar_marine_operations", "sedar_service_order_demo", "sedar_recruitment_crewing", "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sedar_erp_demo_bootstrap.xml",
        "views/sedar_erp_demo_views.xml",
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}

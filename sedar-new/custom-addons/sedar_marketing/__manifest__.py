{
    "name": "SEDAR Marketing",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Customer-centred service request, quotation, contract, appointment, and relationship workspace",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "sedar_marine_operations",
        "sedar_marine_finance",
        "sedar_document_control",
        "sedar_theme",
        "calendar",
        "mail",
    ],
    "data": [
        "security/sedar_marketing_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_marketing_sequences.xml",
        "data/sedar_marketing_data.xml",
        "views/sedar_marketing_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sedar_marketing/static/src/css/sedar_marketing.css",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}

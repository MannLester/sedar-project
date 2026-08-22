{
    "name": "SEDAR Purchase Request",
    "version": "19.0.5.0.0",
    "category": "Purchase",
    "summary": "Department purchase request approval and standard Purchase Order handoff",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "purchase",
        "sedar_marine_inventory",
    ],
    "data": [
        "security/sedar_purchase_request_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_purchase_request_sequence.xml",
        "data/sedar_purchase_bid_sequence.xml",
        "data/sedar_purchase_request_activity.xml",
        "views/sedar_purchase_request_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

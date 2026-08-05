{
    "name": "SEDAR HSSE",
    "version": "19.0.1.0.0",
    "category": "Marine",
    "summary": "HSSE incidents, inspections, risk assessments, permits, meetings, training, and corrective actions",
    "author": "SEDAR Development Team",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "sedar_document_control",
        "sedar_marine_maintenance",
        "sedar_marine_dispatch",
    ],
    "data": [
        "security/sedar_hsse_security.xml",
        "security/ir.model.access.csv",
        "data/sedar_hsse_sequence.xml",
        "views/sedar_hsse_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

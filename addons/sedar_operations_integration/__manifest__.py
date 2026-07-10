{
    'name': 'SEDAR Operations Integration',
    'version': '17.0.1.0.0',
    'summary': 'Connected request-to-cash and operational readiness workflows',
    'category': 'Operations',
    'license': 'LGPL-3',
    'depends': [
        'sedar_marketing',
        'sedar_tug_ops',
        'sedar_crewing',
        'sedar_hsse',
        'sedar_doccontrol',
        'sedar_dashboard',
        'sedar_marine_mvp',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/legacy_view_cleanup.xml',
        'views/workflow_views.xml',
        'views/hse_workflow_views.xml',
        'views/document_workflow_views.xml',
        'data/presentation_data.xml',
        'data/hse_presentation_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_operations_integration/static/src/css/document_risk_dashboard.css',
        ],
    },
    'installable': True,
    'application': False,
}

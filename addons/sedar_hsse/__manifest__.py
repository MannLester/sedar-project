{
    'name': 'SEDAR HSSE',
    'version': '17.0.1.2.0',
    'summary': 'Health, safety, security, and environment records',
    'category': 'Operations',
    'depends': ['base', 'web', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/incident_views.xml',
        'views/near_miss_views.xml',
        'views/inspection_views.xml',
        'views/risk_assessment_views.xml',
        'views/permit_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_hsse/static/src/xml/hsse_dashboard.xml',
            'sedar_hsse/static/src/js/hsse_dashboard.js',
            'sedar_hsse/static/src/css/hsse.css',
        ],
    },
    'installable': True,
    'application': True,
}

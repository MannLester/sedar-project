{
    'name': 'SEDAR HSSE',
    'version': '17.0.1.0.0',
    'summary': 'Health, safety, security, and environment records',
    'category': 'Operations',
    'depends': ['base', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/incident_views.xml',
        'views/near_miss_views.xml',
        'views/inspection_views.xml',
        'views/risk_assessment_views.xml',
        'views/permit_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}

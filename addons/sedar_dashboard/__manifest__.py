{
    'name': 'SEDAR Management Dashboard',
    'version': '17.0.1.1.0',
    'summary': 'Community-compatible KPI snapshot for SEDAR leadership',
    'category': 'Reporting',
    'depends': ['account', 'sedar_tug_ops', 'sedar_hsse', 'sedar_crewing', 'sedar_doccontrol'],
    'data': [
        'security/ir.model.access.csv',
        'data/dashboard_data.xml',
        'views/dashboard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}

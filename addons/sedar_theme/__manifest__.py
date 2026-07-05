{
    'name': 'SEDAR Sidebar Theme',
    'version': '17.0.1.0.0',
    'summary': 'Reference-inspired sidebar theme for the SEDAR Odoo MVP',
    'category': 'Theme/Backend',
    'depends': [
        'web',
        'account',
        'purchase',
        'stock',
        'maintenance',
        'hr',
        'hr_recruitment',
        'sedar_tug_ops',
        'sedar_hsse',
        'sedar_crewing',
        'sedar_doccontrol',
        'sedar_dashboard',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_theme/static/src/xml/sedar_sidebar.xml',
            'sedar_theme/static/src/css/sedar_sidebar.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

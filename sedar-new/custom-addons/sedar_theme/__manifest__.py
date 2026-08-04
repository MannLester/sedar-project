{
    'name': 'SEDAR Sidebar Theme',
    'version': '19.0.1.0.0',
    'summary': 'Reference-inspired sidebar theme for the SEDAR Odoo MVP',
    'author': 'SEDAR Development Team',
    'category': 'Theme/Backend',
    'depends': ['web', 'sedar_document_control', 'sedar_marine_operations', 'sedar_marine_finance'],
    'assets': {
        'web.assets_backend': [
            'sedar_theme/static/src/xml/sedar_sidebar.xml',
            'sedar_theme/static/src/css/sedar_sidebar.css',
        ],
        'web.assets_frontend': [
            'sedar_theme/static/src/css/sedar_login.css',
        ],
    },
    'data': [
        'data/assets.xml',
        'data/default_home_action.xml',
        'views/login_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

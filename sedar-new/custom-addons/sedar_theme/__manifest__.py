{
    'name': 'SEDAR Sidebar Theme',
    'version': '19.0.2.0.0',
    'summary': 'Reference-inspired sidebar theme for the SEDAR Odoo MVP',
    'author': 'SEDAR Development Team',
    'category': 'Theme/Backend',
    'depends': [
        'web',
        'sedar_document_control',
        'sedar_marine_operations',
        'sedar_marine_finance',
        'sedar_purchase_request',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_theme/static/src/xml/sedar_sidebar.xml',
            'sedar_theme/static/src/css/sedar_sidebar.css',
            'sedar_theme/static/src/js/sedar_sidebar_context.js',
            'sedar_theme/static/src/js/disable_push_notifications.js',
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

{
    'name': 'SEDAR Owner Preview',
    'version': '17.0.1.0.0',
    'summary': 'Client-facing visualization of the target SEDAR tug ERP experience',
    'category': 'Reporting',
    'depends': ['web', 'sedar_dashboard', 'sedar_tug_ops', 'sedar_operations_integration'],
    'data': [
        'views/owner_preview_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_owner_preview/static/src/js/owner_preview.js',
            'sedar_owner_preview/static/src/xml/owner_preview.xml',
            'sedar_owner_preview/static/src/css/owner_preview.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

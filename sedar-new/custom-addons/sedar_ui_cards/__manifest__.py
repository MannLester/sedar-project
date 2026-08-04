{
    'name': 'SEDAR UI Cards',
    'version': '19.0.1.0.0',
    'summary': 'Reusable backend card design primitives for SEDAR modules',
    'author': 'SEDAR Development Team',
    'category': 'Technical',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'sedar_ui_cards/static/src/css/sedar_cards.css',
        ],
    },
    'data': ['data/assets.xml'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

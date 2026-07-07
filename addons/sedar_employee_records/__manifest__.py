{
    'name': 'SEDAR Employee Records',
    'version': '17.0.1.0.0',
    'summary': 'Human Resources employee list with tugboat crewing context',
    'category': 'Human Resources',
    'depends': [
        'hr',
        'hr_recruitment',
        'sedar_crewing',
    ],
    'data': [
        'views/hr_employee_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

{
    'name': 'SEDAR Employee Document Control',
    'version': '17.0.1.0.0',
    'summary': 'Read-only employee document expiry control list',
    'category': 'Human Resources',
    'depends': [
        'sedar_crewing',
        'sedar_employee_records',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_document_control_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

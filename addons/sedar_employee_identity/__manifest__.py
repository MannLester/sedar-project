{
    'name': 'SEDAR Employee Identity',
    'version': '17.0.1.0.0',
    'summary': 'Barcode-ready employee identity layer for SEDAR HR records',
    'category': 'Human Resources',
    'depends': [
        'sedar_employee_records',
    ],
    'data': [
        'report/employee_badge_report.xml',
        'views/hr_employee_identity_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

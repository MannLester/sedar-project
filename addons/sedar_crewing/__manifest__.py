{
    'name': 'SEDAR Crewing',
    'version': '17.0.1.0.0',
    'summary': 'Crew roster, rotations, certificates, medicals, and leave',
    'category': 'Human Resources',
    'depends': ['hr', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/crew_member_views.xml',
        'views/rotation_views.xml',
        'views/certification_views.xml',
        'views/medical_views.xml',
        'views/leave_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}

{
    'name': 'SEDAR Applicant Dashboard',
    'version': '17.0.1.1.0',
    'summary': 'Token-based applicant status dashboard for submitted applications',
    'category': 'Human Resources/Recruitment',
    'depends': ['sedar_applicant_portal'],
    'data': [
        'views/applicant_dashboard_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sedar_applicant_dashboard/static/src/css/applicant_dashboard.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

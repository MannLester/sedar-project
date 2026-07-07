{
    'name': 'SEDAR Applicant Portal',
    'version': '17.0.1.0.0',
    'summary': 'Public applicant intake form linked to SEDAR recruitment',
    'category': 'Human Resources/Recruitment',
    'depends': ['sedar_recruitment_link'],
    'data': [
        'security/ir.model.access.csv',
        'views/applicant_profile_views.xml',
        'views/applicant_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sedar_applicant_portal/static/src/css/applicant_portal.css',
            'sedar_applicant_portal/static/src/js/applicant_portal.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

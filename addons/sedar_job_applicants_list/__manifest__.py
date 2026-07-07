{
    'name': 'SEDAR Job Applicants List',
    'version': '17.0.1.0.0',
    'summary': 'Dashboard applicant cards for HR review',
    'category': 'Human Resources/Recruitment',
    'depends': [
        'sedar_dashboard',
        'sedar_recruitment_link',
        'sedar_applicant_portal',
        'sedar_ui_cards',
    ],
    'data': [
        'data/portal_seed_data.xml',
        'views/job_applicants_views.xml',
        'views/job_applications_tab_views.xml',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_job_applicants_list/static/src/css/job_applicants_list.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

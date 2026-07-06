{
    'name': 'SEDAR Job Hiring Workflow',
    'version': '17.0.1.0.0',
    'summary': 'Job dispatch orders and HR hiring workflow for vessel crew gaps',
    'category': 'Human Resources/Recruitment',
    'depends': ['hr_recruitment', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/demo_data.xml',
        'views/job_hiring_overview_views.xml',
        'views/interview_schedule_wizard_views.xml',
        'views/job_dispatch_views.xml',
        'views/hr_applicant_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sedar_recruitment_link/static/src/css/job_hiring.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

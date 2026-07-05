{
    'name': 'SEDAR Document Control',
    'version': '17.0.1.0.0',
    'summary': 'Contracts, vessel certificates, insurance, and controlled documents',
    'category': 'Administration',
    'depends': ['base', 'sedar_base', 'sedar_tug_ops'],
    'data': [
        'security/ir.model.access.csv',
        'views/contract_views.xml',
        'views/vessel_cert_views.xml',
        'views/insurance_views.xml',
        'views/doc_record_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}

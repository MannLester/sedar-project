{
    'name': 'SEDAR Maintenance-Vessel Link',
    'version': '17.0.1.0.0',
    'summary': 'Link Odoo Maintenance equipment records to SEDAR vessels',
    'category': 'Operations',
    'depends': ['maintenance', 'sedar_tug_ops'],
    'data': ['views/maintenance_equipment_views.xml'],
    'installable': True,
    'application': False,
}

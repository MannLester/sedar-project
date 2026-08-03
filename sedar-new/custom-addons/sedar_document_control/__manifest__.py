{
    "name": "SEDAR Document Control",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "SEDAR document catalogue, typed fields, and employee requests",
    "depends": ["base"],
    "data": ["security/ir.model.access.csv", "views/sedar_document_views.xml", "data/sedar_document_data.xml", "data/sedar_document_fields.xml"],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
    "author": "SEDAR Development Team",
}

from odoo import fields, models, tools


class SedarEmployeeDocumentControl(models.Model):
    _name = 'sedar.employee.document.control'
    _description = 'Employee Document Control'
    _auto = False
    _order = 'expiry_date, employee_id, document_type'

    employee_id = fields.Many2one('hr.employee.public', string='Employee', readonly=True)
    crew_id = fields.Many2one('sedar.crew.member', string='Crew Record', readonly=True)
    current_vessel_id = fields.Many2one('sedar.vessel', string='Current Boat', readonly=True)
    rank = fields.Char(string='Rank/Position', readonly=True)
    document_type = fields.Selection(
        [
            ('certification', 'Certification'),
            ('medical', 'Medical'),
        ],
        string='Document Type',
        readonly=True,
    )
    document_name = fields.Char(string='Document', readonly=True)
    document_no = fields.Char(string='Document No.', readonly=True)
    issue_date = fields.Date(string='Issue/Exam Date', readonly=True)
    expiry_date = fields.Date(string='Expiry Date', readonly=True)
    days_to_expiry = fields.Integer(string='Days to Expiry', readonly=True)
    expiry_status = fields.Selection(
        [
            ('warning', 'Expiring Soon'),
            ('expired', 'Expired'),
        ],
        string='Status',
        readonly=True,
    )
    source_model = fields.Char(string='Source Model', readonly=True)
    source_id = fields.Integer(string='Source ID', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    certification.id * 2 - 1 AS id,
                    crew.employee_id AS employee_id,
                    crew.id AS crew_id,
                    crew.vessel_id AS current_vessel_id,
                    crew.rank AS rank,
                    'certification'::varchar AS document_type,
                    certification.cert_type AS document_name,
                    certification.certificate_no AS document_no,
                    certification.issue_date AS issue_date,
                    certification.expiry_date AS expiry_date,
                    (certification.expiry_date - CURRENT_DATE)::integer AS days_to_expiry,
                    CASE
                        WHEN certification.expiry_date < CURRENT_DATE THEN 'expired'
                        ELSE 'warning'
                    END::varchar AS expiry_status,
                    'sedar.crew.certification'::varchar AS source_model,
                    certification.id AS source_id
                FROM sedar_crew_certification certification
                JOIN sedar_crew_member crew ON crew.id = certification.crew_id
                WHERE certification.expiry_date IS NOT NULL
                  AND certification.expiry_date <= CURRENT_DATE + INTERVAL '90 days'

                UNION ALL

                SELECT
                    medical.id * 2 AS id,
                    crew.employee_id AS employee_id,
                    crew.id AS crew_id,
                    crew.vessel_id AS current_vessel_id,
                    crew.rank AS rank,
                    'medical'::varchar AS document_type,
                    'Medical Certificate'::varchar AS document_name,
                    medical.clinic AS document_no,
                    medical.exam_date AS issue_date,
                    medical.expiry_date AS expiry_date,
                    (medical.expiry_date - CURRENT_DATE)::integer AS days_to_expiry,
                    CASE
                        WHEN medical.expiry_date < CURRENT_DATE THEN 'expired'
                        ELSE 'warning'
                    END::varchar AS expiry_status,
                    'sedar.crew.medical'::varchar AS source_model,
                    medical.id AS source_id
                FROM sedar_crew_medical medical
                JOIN sedar_crew_member crew ON crew.id = medical.crew_id
                WHERE medical.expiry_date IS NOT NULL
                  AND medical.expiry_date <= CURRENT_DATE + INTERVAL '90 days'
            )
        """ % self._table)

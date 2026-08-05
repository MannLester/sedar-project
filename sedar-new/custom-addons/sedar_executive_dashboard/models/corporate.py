from datetime import date

from odoo import Command, api, fields, models


class SedarDocument(models.Model):
    _inherit = "sedar.document"

    document_category = fields.Selection([
        ("corporate", "Corporate Governance"),
        ("vessel", "Vessel / Fleet"),
        ("commercial", "Commercial"),
        ("hse", "HSSE"),
        ("hr", "Human Resources"),
    ], default="corporate", required=True)
    owner_id = fields.Many2one("res.users", string="Document Owner", ondelete="restrict")
    valid_from = fields.Date()
    valid_until = fields.Date()
    renewal_date = fields.Date()
    approval_state = fields.Selection([
        ("pending", "Pending Approval"), ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="approved", required=True)
    confidential = fields.Boolean()
    partner_id = fields.Many2one("res.partner", string="Related Partner", ondelete="set null")
    tugboat_id = fields.Many2one("sedar.tugboat", string="Related Tugboat", ondelete="set null")
    governance_status = fields.Selection([
        ("current", "Current"), ("renewal_due", "Renewal Due"),
        ("expired", "Expired"), ("no_expiry", "No Expiry"),
    ], compute="_compute_governance_status", store=True)

    @api.depends("valid_until", "renewal_date", "approval_state", "state")
    def _compute_governance_status(self):
        today = fields.Date.context_today(self)
        warning_date = fields.Date.add(today, days=30)
        for document in self:
            if document.approval_state != "approved" or document.state != "active":
                document.governance_status = "current"
            elif not document.valid_until:
                document.governance_status = "no_expiry"
            elif document.valid_until < today:
                document.governance_status = "expired"
            elif document.renewal_date and document.renewal_date <= warning_date:
                document.governance_status = "renewal_due"
            elif document.valid_until <= warning_date:
                document.governance_status = "renewal_due"
            else:
                document.governance_status = "current"


class SedarCorporateRecord(models.Model):
    _name = "sedar.corporate.record"
    _description = "SEDAR Corporate Governance Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "valid_until, name"

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(required=True, index=True, tracking=True)
    record_type = fields.Selection([
        ("contract", "Contract"), ("vessel_certificate", "Vessel Certificate"),
        ("insurance", "Insurance Policy"), ("board_resolution", "Board Resolution"),
        ("iso_document", "ISO Document"), ("legal_case", "Legal Case"),
        ("internal_audit", "Internal Audit"), ("permit", "Corporate Permit"),
    ], required=True, tracking=True)
    document_id = fields.Many2one("sedar.document", required=True, ondelete="restrict")
    owner_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", ondelete="set null")
    tugboat_id = fields.Many2one("sedar.tugboat", ondelete="set null")
    state = fields.Selection([
        ("draft", "Draft"), ("active", "Active"), ("under_review", "Under Review"),
        ("closed", "Closed"),
    ], default="active", required=True, tracking=True)
    approval_state = fields.Selection([
        ("pending", "Pending Approval"), ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="approved", required=True, tracking=True)
    valid_from = fields.Date()
    valid_until = fields.Date()
    renewal_date = fields.Date()
    confidential = fields.Boolean()
    description = fields.Text()
    next_action = fields.Char()
    compliance_status = fields.Selection([
        ("current", "Current"), ("renewal_due", "Renewal Due"),
        ("expired", "Expired"), ("no_expiry", "No Expiry"),
    ], compute="_compute_compliance_status", store=True)
    days_to_expiry = fields.Integer(compute="_compute_compliance_status", store=True)

    @api.depends("valid_until", "renewal_date", "state", "approval_state")
    def _compute_compliance_status(self):
        today = fields.Date.context_today(self)
        warning_date = fields.Date.add(today, days=30)
        for record in self:
            if not record.valid_until:
                record.compliance_status = "no_expiry"
                record.days_to_expiry = 0
            else:
                record.days_to_expiry = (record.valid_until - today).days
                if record.valid_until < today:
                    record.compliance_status = "expired"
                elif record.renewal_date and record.renewal_date <= warning_date:
                    record.compliance_status = "renewal_due"
                elif record.valid_until <= warning_date:
                    record.compliance_status = "renewal_due"
                else:
                    record.compliance_status = "current"


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_ensure_executive_demo(self):
        from .dashboard import _record
        import base64

        env = self.env
        company = env.company
        owner = env.user
        executive_group = env.ref("sedar_executive_dashboard.group_sedar_executive")
        executive_user = _record(env, "res.users", "user_executive_demo", {
            "name": "Demo SEDAR President", "login": "executive@sedar.demo",
            "password": "executivedemo", "company_id": company.id,
            "company_ids": [Command.set([company.id])],
            "group_ids": [Command.set([env.ref("base.group_user").id, executive_group.id])],
        })
        types = {
            "contract": "Corporate Contract", "vessel_certificate": "Vessel Certificate",
            "insurance": "Marine Insurance Policy", "board_resolution": "Board Resolution",
            "iso_document": "ISO Controlled Document", "legal_case": "Legal Case",
            "internal_audit": "Internal Audit Record",
        }
        for code, name in types.items():
            _record(env, "sedar.document.type", f"document_type_corporate_{code}", {
                "name": name, "code": f"CORP-{code.upper()}",
                "department": "Executive Management / Corporate Governance",
                "description": f"Demonstration catalogue entry for {name.lower()}.",
                "approval_status": "approved", "field_definition": "Owner; status; validity; renewal; approval; confidentiality; related business object; supporting source file.",
            })
        client = env["res.partner"].search([("is_company", "=", True)], order="id", limit=1)
        tug = env["sedar.tugboat"].search([], order="id", limit=1)
        specs = [
            ("contract", "CON-2026-001", "Port Services Master Agreement", "2026-01-01", "2026-12-31", "2026-12-01", False, client, False),
            ("vessel_certificate", "CERT-TUG-001", "Certificate of Registry - Demo Tug", "2025-01-01", "2026-08-20", "2026-07-21", False, False, tug),
            ("insurance", "INS-2026-001", "Hull and Machinery Insurance", "2026-01-01", "2026-12-31", "2026-12-01", False, client, tug),
            ("board_resolution", "BR-2026-003", "Approval of Digital Transformation Program", "2026-07-01", False, False, True, False, False),
            ("iso_document", "ISO-PROC-001", "Marine Operations Quality Procedure", "2026-01-01", False, False, False, False, False),
            ("legal_case", "LEGAL-2026-001", "Demo Contract Review Matter", "2026-07-10", False, False, True, client, False),
            ("internal_audit", "AUDIT-2026-001", "Marine Safety and Document Control Audit", "2026-07-15", "2026-08-30", "2026-08-15", False, False, tug),
        ]
        for record_type, reference, title, valid_from, valid_until, renewal_date, confidential, partner, related_tug in specs:
            document_type = env.ref(f"sedar_executive_dashboard.document_type_corporate_{record_type}")
            document = _record(env, "sedar.document", f"controlled_corporate_{record_type}", {
                "name": title, "document_type_id": document_type.id,
                "file": base64.b64encode((f"SEDAR DEMONSTRATION SOURCE\n{reference}\n{title}\n").encode()).decode(),
                "filename": f"{reference}.txt", "document_category": "corporate" if record_type not in {"vessel_certificate"} else "vessel",
                "owner_id": executive_user.id, "valid_from": valid_from, "valid_until": valid_until or False,
                "renewal_date": renewal_date or False, "approval_state": "approved", "confidential": confidential,
                "partner_id": partner.id if partner else False, "tugboat_id": related_tug.id if related_tug else False,
            })
            _record(env, "sedar.corporate.record", f"corporate_record_{record_type}", {
                "name": title, "reference": reference, "record_type": record_type,
                "document_id": document.id, "owner_id": executive_user.id,
                "partner_id": partner.id if partner else False, "tugboat_id": related_tug.id if related_tug else False,
                "valid_from": valid_from, "valid_until": valid_until or False, "renewal_date": renewal_date or False,
                "confidential": confidential, "state": "active", "approval_state": "approved",
                "description": f"Demonstration-only {title.lower()} for the SEDAR proposal walkthrough.",
                "next_action": "Review with the responsible owner before production adoption.",
            })
        _record(env, "sedar.executive.dashboard", "executive_dashboard_demo", {
            "name": "SEDAR Executive Management Dashboard", "company_id": company.id,
            "last_refreshed": fields.Datetime.now(),
        })
        return True


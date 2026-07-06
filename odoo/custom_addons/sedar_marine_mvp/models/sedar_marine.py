from odoo import api, fields, models


class SedarDashboardMetric(models.Model):
    _name = "sedar.dashboard.metric"
    _description = "SEDAR Dashboard Metric"
    _order = "sequence, name"

    name = fields.Char(required=True)
    module_area = fields.Selection(
        [
            ("finance", "Finance and Accounting"),
            ("operations", "Tug Operations"),
            ("maintenance", "Technical and Maintenance"),
            ("hse", "Health, Safety, Security and Environment"),
            ("crewing", "Crewing"),
            ("procurement", "Procurement"),
            ("inventory", "Inventory"),
            ("hr", "Human Resources"),
            ("marketing", "Marketing"),
            ("corporate", "Corporate Management"),
            ("documents", "Document Control"),
            ("management", "Management Dashboard"),
        ],
        required=True,
    )
    value = fields.Char(required=True)
    unit = fields.Char()
    status = fields.Selection(
        [("good", "Good"), ("watch", "Watch"), ("risk", "Risk")],
        default="good",
        required=True,
    )
    sequence = fields.Integer(default=10)
    note = fields.Text()


class SedarVessel(models.Model):
    _name = "sedar.vessel"
    _description = "SEDAR Vessel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    registry_no = fields.Char()
    vessel_type = fields.Selection(
        [
            ("harbor_tug", "Harbor Tug"),
            ("tow_tug", "Tow Tug"),
            ("support", "Support Vessel"),
        ],
        default="harbor_tug",
    )
    horsepower = fields.Integer()
    bollard_pull = fields.Float(string="Bollard Pull")
    home_port = fields.Char()
    status = fields.Selection(
        [
            ("available", "Available"),
            ("assigned", "Assigned"),
            ("maintenance", "Under Maintenance"),
            ("dry_dock", "Dry Dock"),
            ("off_hire", "Off-Hire"),
        ],
        default="available",
        tracking=True,
    )
    utilization_rate = fields.Float(string="Utilization %")
    availability_rate = fields.Float(string="Availability %")
    fuel_on_hand = fields.Float()
    last_known_location = fields.Char()
    ais_timestamp = fields.Datetime(string="GPS/AIS Timestamp")
    certificate_expiry = fields.Date()
    insurance_expiry = fields.Date()
    job_ids = fields.One2many("sedar.job.order", "vessel_id")
    maintenance_ids = fields.One2many("sedar.maintenance.work.order", "vessel_id")


class SedarCustomer(models.Model):
    _name = "sedar.customer"
    _description = "SEDAR Customer"
    _order = "name"

    name = fields.Char(required=True)
    customer_type = fields.Selection(
        [
            ("shipping", "Shipping Line"),
            ("terminal", "Terminal"),
            ("industrial", "Industrial"),
            ("government", "Government"),
        ],
        default="shipping",
    )
    billing_terms = fields.Char(default="30 days")
    contract_status = fields.Selection(
        [("active", "Active"), ("renewal", "For Renewal"), ("expired", "Expired")],
        default="active",
    )
    receivable_balance = fields.Float()
    margin_rate = fields.Float(string="Margin %")


class SedarJobOrder(models.Model):
    _name = "sedar.job.order"
    _description = "SEDAR Job Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "requested_datetime desc, name"

    name = fields.Char(required=True, tracking=True)
    customer_id = fields.Many2one("sedar.customer", required=True)
    service_type = fields.Selection(
        [
            ("ship_assist", "Ship Assist"),
            ("barge_tow", "Barge Tow"),
            ("escort", "Escort"),
            ("standby", "Standby"),
            ("emergency", "Emergency/Special Operation"),
            ("terminal", "Terminal Support"),
        ],
        required=True,
    )
    vessel_id = fields.Many2one("sedar.vessel")
    requested_datetime = fields.Datetime()
    scheduled_datetime = fields.Datetime()
    origin = fields.Char()
    destination = fields.Char()
    status = fields.Selection(
        [
            ("requested", "Requested"),
            ("quoted", "Quoted"),
            ("approved", "Approved"),
            ("scheduled", "Scheduled"),
            ("dispatched", "Dispatched"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("billed", "Billed"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="requested",
        tracking=True,
    )
    delay_reason = fields.Char()
    billable_amount = fields.Float()
    direct_cost = fields.Float()
    gross_margin = fields.Float(compute="_compute_gross_margin", store=True)
    expected_fuel_used = fields.Float()
    fuel_variance = fields.Float(compute="_compute_fuel_variance", store=True)
    voyage_log_ids = fields.One2many("sedar.voyage.log", "job_id")
    invoice_ids = fields.One2many("sedar.finance.record", "job_id")

    @api.depends("billable_amount", "direct_cost")
    def _compute_gross_margin(self):
        for record in self:
            record.gross_margin = record.billable_amount - record.direct_cost

    @api.depends("expected_fuel_used", "voyage_log_ids.fuel_used")
    def _compute_fuel_variance(self):
        for record in self:
            actual_fuel = sum(record.voyage_log_ids.mapped("fuel_used"))
            record.fuel_variance = actual_fuel - record.expected_fuel_used


class SedarVoyageLog(models.Model):
    _name = "sedar.voyage.log"
    _description = "SEDAR Voyage Log"
    _order = "start_datetime desc"

    name = fields.Char(required=True)
    job_id = fields.Many2one("sedar.job.order", required=True)
    vessel_id = fields.Many2one(related="job_id.vessel_id", store=True)
    start_datetime = fields.Datetime()
    end_datetime = fields.Datetime()
    voyage_hours = fields.Float()
    fuel_used = fields.Float()
    waiting_hours = fields.Float()
    remarks = fields.Text()


class SedarFinanceRecord(models.Model):
    _name = "sedar.finance.record"
    _description = "SEDAR Finance Record"
    _order = "invoice_date desc, name"

    name = fields.Char(required=True)
    record_type = fields.Selection(
        [
            ("gl", "General Ledger"),
            ("ar", "Accounts Receivable"),
            ("ap", "Accounts Payable"),
            ("budget", "Budgeting"),
            ("cash", "Cash Flow"),
            ("asset", "Fixed Assets"),
            ("payroll", "Payroll"),
        ],
        required=True,
    )
    customer_id = fields.Many2one("sedar.customer")
    job_id = fields.Many2one("sedar.job.order")
    supplier = fields.Char()
    budget_category = fields.Char()
    cash_impact = fields.Selection(
        [("inflow", "Inflow"), ("outflow", "Outflow"), ("none", "No Cash Impact")],
        default="none",
    )
    asset_category = fields.Char()
    payroll_group = fields.Char()
    amount = fields.Float()
    invoice_date = fields.Date()
    due_date = fields.Date()
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("overdue", "Overdue"),
            ("paid", "Paid"),
        ],
        default="draft",
    )
    aging_bucket = fields.Selection(
        [
            ("current", "Current"),
            ("30", "1-30 Days"),
            ("60", "31-60 Days"),
            ("90", "61-90 Days"),
            ("over90", "Over 90 Days"),
        ]
    )
    note = fields.Text()


class SedarCrewMember(models.Model):
    _name = "sedar.crew.member"
    _description = "SEDAR Crew Member"
    _order = "name"

    name = fields.Char(required=True)
    rank = fields.Char()
    availability = fields.Selection(
        [
            ("available", "Available"),
            ("assigned", "Assigned"),
            ("leave", "On Leave"),
            ("training", "Training"),
        ],
        default="available",
    )
    vessel_id = fields.Many2one("sedar.vessel")
    stcw_expiry = fields.Date(string="STCW Expiry")
    medical_expiry = fields.Date()
    certificate_status = fields.Selection(
        [("valid", "Valid"), ("expiring", "Expiring Soon"), ("expired", "Expired")],
        default="valid",
    )
    payroll_group = fields.Char()
    schedule_note = fields.Char()
    leave_start = fields.Date()
    leave_end = fields.Date()
    certificate_ids = fields.One2many("sedar.crew.certificate", "crew_id")


class SedarCrewCertificate(models.Model):
    _name = "sedar.crew.certificate"
    _description = "SEDAR Crew Certificate"

    name = fields.Char(required=True)
    crew_id = fields.Many2one("sedar.crew.member", required=True)
    certificate_type = fields.Selection(
        [
            ("stcw", "STCW"),
            ("medical", "Medical"),
            ("training", "Training"),
            ("license", "License"),
        ],
        default="stcw",
    )
    expiry_date = fields.Date()
    status = fields.Selection(
        [("valid", "Valid"), ("expiring", "Expiring Soon"), ("expired", "Expired")],
        default="valid",
    )


class SedarMaintenanceWorkOrder(models.Model):
    _name = "sedar.maintenance.work.order"
    _description = "SEDAR Maintenance Work Order"
    _order = "due_date, name"

    name = fields.Char(required=True)
    vessel_id = fields.Many2one("sedar.vessel", required=True)
    work_type = fields.Selection(
        [
            ("planned", "Planned Maintenance"),
            ("defect", "Defect"),
            ("dry_dock", "Dry Dock"),
        ],
        default="planned",
    )
    equipment = fields.Char()
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
    )
    due_date = fields.Date()
    dry_dock_window = fields.Char()
    assigned_owner = fields.Char()
    downtime_hours = fields.Float()
    cost = fields.Float()
    status = fields.Selection(
        [
            ("open", "Open"),
            ("waiting_parts", "Waiting Parts"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("overdue", "Overdue"),
        ],
        default="open",
    )
    spare_parts_note = fields.Text()
    equipment_history = fields.Text()


class SedarHseRecord(models.Model):
    _name = "sedar.hse.record"
    _description = "SEDAR HSE Record"
    _order = "event_date desc, name"

    name = fields.Char(required=True)
    record_type = fields.Selection(
        [
            ("incident", "Incident Reporting"),
            ("near_miss", "Near Miss"),
            ("inspection", "Inspection"),
            ("permit", "Permit"),
            ("audit", "Audit"),
            ("risk", "Risk Assessment"),
            ("training", "Training Record"),
        ],
        required=True,
    )
    vessel_id = fields.Many2one("sedar.vessel")
    job_id = fields.Many2one("sedar.job.order")
    event_date = fields.Date()
    risk_level = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium"
    )
    corrective_action = fields.Text()
    training_participant = fields.Char()
    audit_reference = fields.Char()
    responsible_person = fields.Char()
    due_date = fields.Date()
    status = fields.Selection(
        [
            ("open", "Open"),
            ("in_progress", "In Progress"),
            ("closed", "Closed"),
            ("overdue", "Overdue"),
        ],
        default="open",
    )


class SedarProcurementRecord(models.Model):
    _name = "sedar.procurement.record"
    _description = "SEDAR Procurement Record"
    _order = "request_date desc, name"

    name = fields.Char(required=True)
    record_type = fields.Selection(
        [("pr", "Purchase Request"), ("po", "Purchase Order")], default="pr"
    )
    supplier = fields.Char()
    requested_by = fields.Char()
    request_date = fields.Date()
    amount = fields.Float()
    expected_delivery = fields.Date()
    approval_age_days = fields.Integer()
    supplier_lead_days = fields.Integer()
    delivery_performance = fields.Selection(
        [("good", "Good"), ("watch", "Watch"), ("risk", "Risk")],
        default="good",
    )
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("ordered", "Ordered"),
            ("received", "Received"),
        ],
        default="draft",
    )
    approval_owner = fields.Char()
    maintenance_id = fields.Many2one("sedar.maintenance.work.order")
    inventory_id = fields.Many2one("sedar.inventory.item")
    note = fields.Text()


class SedarInventoryItem(models.Model):
    _name = "sedar.inventory.item"
    _description = "SEDAR Inventory Item"
    _order = "category, name"

    name = fields.Char(required=True)
    category = fields.Selection(
        [
            ("spare", "Spare Parts"),
            ("fuel", "Fuel"),
            ("lubricant", "Lubricants"),
            ("office", "Office Supplies"),
        ],
        default="spare",
    )
    warehouse = fields.Char()
    location_bin = fields.Char(string="Location/Bin")
    barcode = fields.Char()
    quantity_on_hand = fields.Float()
    reorder_point = fields.Float()
    unit_cost = fields.Float()
    stock_value = fields.Float(compute="_compute_stock_value", store=True)
    status = fields.Selection(
        [("ok", "OK"), ("low", "Low Stock"), ("critical", "Critical")], default="ok"
    )
    maintenance_demand = fields.Char()
    procurement_signal = fields.Char()

    @api.depends("quantity_on_hand", "unit_cost")
    def _compute_stock_value(self):
        for record in self:
            record.stock_value = record.quantity_on_hand * record.unit_cost


class SedarHrRecord(models.Model):
    _name = "sedar.hr.record"
    _description = "SEDAR HR Record"
    _order = "name"

    name = fields.Char(required=True)
    department = fields.Char()
    record_type = fields.Selection(
        [
            ("employee", "Employee Records"),
            ("attendance", "Attendance"),
            ("performance", "Performance Evaluation"),
            ("recruitment", "Recruitment"),
        ],
        default="employee",
    )
    status = fields.Selection(
        [
            ("active", "Active"),
            ("pending", "Pending"),
            ("due", "Due"),
            ("closed", "Closed"),
        ],
        default="active",
    )
    attendance_date = fields.Date()
    attendance_status = fields.Selection(
        [("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("review", "Pending Review")]
    )
    evaluation_due_date = fields.Date()
    recruitment_role = fields.Char()
    recruitment_stage = fields.Char()
    summary = fields.Text()


class SedarDocumentControl(models.Model):
    _name = "sedar.document.control"
    _description = "SEDAR Document Control"
    _order = "expiry_date, name"

    name = fields.Char(required=True)
    document_type = fields.Selection(
        [
            ("contract", "Contracts"),
            ("vessel_certificate", "Vessel Certificates"),
            ("insurance", "Insurance"),
            ("permit", "Permits"),
            ("board_resolution", "Board Resolutions"),
            ("iso", "ISO Documents"),
        ],
        required=True,
    )
    owner_department = fields.Char()
    vessel_id = fields.Many2one("sedar.vessel")
    expiry_date = fields.Date()
    renewal_owner = fields.Char()
    status = fields.Selection(
        [("valid", "Valid"), ("renewal", "For Renewal"), ("expired", "Expired")],
        default="valid",
    )
    version = fields.Char(default="1.0")
    approval_status = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved"), ("for_review", "For Review")],
        default="approved",
    )
    document_link = fields.Char()


class SedarMarketingRecord(models.Model):
    _name = "sedar.marketing.record"
    _description = "SEDAR Marketing Record"
    _order = "name"

    name = fields.Char(required=True)
    record_type = fields.Selection(
        [
            ("customer_pipeline", "Customer Pipeline"),
            ("customer_satisfaction", "Customer Satisfaction"),
            ("service_proposal", "Service Proposal"),
            ("client_feedback", "Client Feedback"),
        ],
        default="customer_pipeline",
        required=True,
    )
    customer_id = fields.Many2one("sedar.customer")
    service_type = fields.Selection(
        [
            ("ship_assist", "Ship Assist"),
            ("barge_tow", "Barge Tow"),
            ("escort", "Escort"),
            ("standby", "Standby"),
            ("emergency", "Emergency/Special Operation"),
            ("terminal", "Terminal Support"),
        ],
    )
    opportunity_value = fields.Float()
    status = fields.Selection(
        [
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("proposal", "Proposal"),
            ("won", "Won"),
            ("lost", "Lost"),
            ("follow_up", "Follow Up"),
        ],
        default="new",
    )
    owner = fields.Char()
    next_action_date = fields.Date()
    satisfaction_score = fields.Float()
    note = fields.Text()


class SedarCorporateRecord(models.Model):
    _name = "sedar.corporate.record"
    _description = "SEDAR Corporate Management Record"
    _order = "record_type, name"

    name = fields.Char(required=True)
    record_type = fields.Selection(
        [
            ("board_resolution", "Board Resolutions"),
            ("legal_case", "Legal Cases"),
            ("insurance", "Insurance"),
            ("contract", "Contracts"),
            ("internal_audit", "Internal Audit"),
            ("kpi_dashboard", "KPI Dashboard"),
            ("recommended_system", "Recommended System"),
            ("essential_program", "Other Essential Program"),
        ],
        required=True,
    )
    owner_department = fields.Char()
    responsible_person = fields.Char()
    due_date = fields.Date()
    status = fields.Selection(
        [
            ("active", "Active"),
            ("for_review", "For Review"),
            ("pending", "Pending"),
            ("closed", "Closed"),
            ("risk", "Risk"),
        ],
        default="active",
    )
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
    )
    value = fields.Char()
    note = fields.Text()

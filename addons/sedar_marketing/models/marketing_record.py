from odoo import api, fields, models


class SedarCustomer(models.Model):
    _inherit = "sedar.customer"

    marketing_contact_person = fields.Char()
    marketing_mobile_number = fields.Char()
    marketing_telephone_number = fields.Char()
    marketing_company_address = fields.Char()


class SedarMarketingRecord(models.Model):
    _name = "sedar.marketing.record"
    _description = "SEDAR Marketing Customer Support Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, name"

    def init(self):
        self.env.cr.execute(
            """
            INSERT INTO sedar_customer (name, customer_type, billing_terms, contract_status, receivable_balance, margin_rate)
            SELECT DISTINCT smr.company_name, 'shipping', '30 days', 'active', 0, 0
              FROM sedar_marketing_record smr
         LEFT JOIN sedar_customer sc ON lower(sc.name) = lower(smr.company_name)
             WHERE smr.company_name IS NOT NULL
               AND smr.company_name != ''
               AND sc.id IS NULL
            """
        )
        self.env.cr.execute(
            """
            UPDATE sedar_customer sc
               SET marketing_contact_person = COALESCE(NULLIF(sc.marketing_contact_person, ''), latest.contact_person),
                   marketing_mobile_number = COALESCE(NULLIF(sc.marketing_mobile_number, ''), latest.mobile_number),
                   marketing_telephone_number = COALESCE(NULLIF(sc.marketing_telephone_number, ''), latest.telephone_number),
                   marketing_company_address = COALESCE(NULLIF(sc.marketing_company_address, ''), latest.company_address)
              FROM (
                    SELECT DISTINCT ON (lower(company_name)) company_name,
                           contact_person,
                           mobile_number,
                           telephone_number,
                           company_address
                      FROM sedar_marketing_record
                     WHERE company_name IS NOT NULL
                       AND company_name != ''
                  ORDER BY lower(company_name), write_date DESC NULLS LAST, create_date DESC NULLS LAST
                   ) latest
             WHERE lower(sc.name) = lower(latest.company_name)
            """
        )

    name = fields.Char(default="New Customer Support Request", required=True, tracking=True)
    flow_step = fields.Selection(
        [
            ("customer", "Customer"),
            ("requirements", "Requirements"),
            ("vessel_info", "Vessel Info"),
            ("review", "Review"),
        ],
        default="customer",
        required=True,
        tracking=True,
    )
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
    customer_id = fields.Many2one("sedar.customer", string="Search Existing Customer")
    company_name = fields.Char()
    contact_person = fields.Char()
    mobile_number = fields.Char()
    telephone_number = fields.Char()
    company_address = fields.Char()
    communication_method = fields.Selection(
        [
            ("email", "Email"),
            ("phone", "Phone"),
            ("whatsapp", "Whatsapp"),
            ("viber", "Viber"),
            ("face_to_face", "Face-to-face"),
        ],
        default="phone",
        string="Preferred Communication Method",
        required=True,
    )
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
    purpose_of_request = fields.Char()
    requested_date = fields.Date()
    requested_time = fields.Selection(
        [(f"{hour:02d}:{minute:02d}", f"{hour:02d}:{minute:02d}") for hour in range(24) for minute in (0, 30)]
    )
    pickup_location = fields.Char()
    destination = fields.Char()
    estimated_duration = fields.Char()
    tugboats_requested = fields.Integer(default=1)
    priority_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("urgent", "Urgent"),
            ("emergency", "Emergency"),
        ],
        default="urgent",
    )
    vessel_name = fields.Char()
    vessel_type = fields.Char()
    imo_number = fields.Char(string="IMO Number")
    cargo_type = fields.Char()
    gross_tonnage = fields.Float()
    length_overall = fields.Float()
    beam = fields.Float()
    draft = fields.Float()
    current_location = fields.Char()
    destination_location = fields.Char()
    opportunity_value = fields.Float()
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("pending_review", "Pending Review"),
            ("drafting_quote", "Drafting Quote"),
            ("pending_approval", "Pending Approval"),
            ("for_signature", "For Signature"),
            ("scheduled", "Scheduled"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("proposal", "Proposal"),
            ("won", "Won"),
            ("lost", "Lost"),
            ("follow_up", "Follow Up"),
        ],
        default="new",
        tracking=True,
    )
    owner = fields.Char()
    next_action_date = fields.Date()
    satisfaction_score = fields.Float()
    note = fields.Text()

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        for record in self:
            if record.customer_id:
                record.company_name = record.customer_id.name
                record.contact_person = record.customer_id.marketing_contact_person
                record.mobile_number = record.customer_id.marketing_mobile_number
                record.telephone_number = record.customer_id.marketing_telephone_number
                record.company_address = record.customer_id.marketing_company_address

    def _sync_customer(self):
        for record in self:
            if not record.company_name:
                continue
            customer = record.customer_id or self.env["sedar.customer"].search(
                [("name", "=ilike", record.company_name)], limit=1
            )
            if not customer:
                customer = self.env["sedar.customer"].create({"name": record.company_name})
            customer.write(
                {
                    "marketing_contact_person": record.contact_person or customer.marketing_contact_person,
                    "marketing_mobile_number": record.mobile_number or customer.marketing_mobile_number,
                    "marketing_telephone_number": record.telephone_number or customer.marketing_telephone_number,
                    "marketing_company_address": record.company_address or customer.marketing_company_address,
                }
            )
            if record.customer_id != customer:
                record.customer_id = customer.id

    def action_save_draft(self):
        self._sync_customer()
        self.write({"status": "draft"})
        return self.env.ref("sedar_marketing.action_sedar_marketing_drafts_board").read()[0]

    def action_next_step(self):
        next_steps = {
            "customer": "requirements",
            "requirements": "vessel_info",
            "vessel_info": "review",
            "review": "review",
        }
        for record in self:
            if record.flow_step == "customer":
                record._sync_customer()
            record.write({"flow_step": next_steps.get(record.flow_step, "requirements"), "status": "in_progress"})
        return True

    def action_previous_step(self):
        previous_steps = {
            "requirements": "customer",
            "vessel_info": "requirements",
            "review": "vessel_info",
            "customer": "customer",
        }
        for record in self:
            record.write({"flow_step": previous_steps.get(record.flow_step, "customer")})
        return True

    def action_submit_request(self):
        self._sync_customer()
        self.write({"flow_step": "review", "status": "pending_review"})
        return self.env.ref("sedar_marketing.action_sedar_marketing_dashboard").read()[0]


class SedarMarketingAppointment(models.Model):
    _name = "sedar.marketing.appointment"
    _description = "SEDAR Marketing Appointment"
    _order = "start_datetime"

    name = fields.Char(required=True, default="Client Appointment")
    request_id = fields.Many2one("sedar.marketing.record", string="Service Request")
    customer_id = fields.Many2one("sedar.customer", string="Customer")
    company_name = fields.Char(required=True)
    contact_person = fields.Char()
    appointment_type = fields.Selection(
        [
            ("client_meeting", "Client Meeting"),
            ("site_visit", "Site Visit"),
            ("contract_signing", "Contract Signing"),
            ("follow_up", "Follow-up"),
        ],
        default="client_meeting",
        required=True,
    )
    start_datetime = fields.Datetime(required=True)
    end_datetime = fields.Datetime(required=True)
    location = fields.Char()
    notes = fields.Text()
    color = fields.Integer(compute="_compute_color")

    @api.onchange("request_id")
    def _onchange_request_id(self):
        for appointment in self:
            if appointment.request_id:
                appointment.customer_id = appointment.request_id.customer_id
                appointment.company_name = appointment.request_id.company_name
                appointment.contact_person = appointment.request_id.contact_person
                appointment.name = appointment.request_id.purpose_of_request or appointment.request_id.name

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        for appointment in self:
            if appointment.customer_id and not appointment.company_name:
                appointment.company_name = appointment.customer_id.name

    @api.depends("appointment_type")
    def _compute_color(self):
        colors = {
            "client_meeting": 10,
            "site_visit": 4,
            "contract_signing": 2,
            "follow_up": 3,
        }
        for appointment in self:
            appointment.color = colors.get(appointment.appointment_type, 0)

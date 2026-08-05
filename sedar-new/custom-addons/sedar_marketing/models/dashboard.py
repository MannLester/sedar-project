from odoo import api, fields, models


class SedarMarketingDashboard(models.Model):
    _name = "sedar.marketing.dashboard"
    _description = "SEDAR Marketing Dashboard"

    name = fields.Char(default="Marketing Dashboard", required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    service_request_count = fields.Integer(compute="_compute_dashboard")
    pending_service_request_count = fields.Integer(compute="_compute_dashboard")
    quotation_count = fields.Integer(compute="_compute_dashboard")
    pending_quotation_count = fields.Integer(compute="_compute_dashboard")
    contract_count = fields.Integer(compute="_compute_dashboard")
    active_contract_count = fields.Integer(compute="_compute_dashboard")
    completed_service_count = fields.Integer(compute="_compute_dashboard")
    today_appointment_count = fields.Integer(compute="_compute_dashboard")
    upcoming_appointment_id = fields.Many2one("calendar.event", compute="_compute_dashboard")
    recent_activity_ids = fields.Many2many("sedar.marketing.activity", compute="_compute_dashboard")
    recent_note_ids = fields.Many2many("sedar.marketing.internal.note", compute="_compute_dashboard")

    @api.depends_context("uid", "company")
    def _compute_dashboard(self):
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        day_start = fields.Datetime.to_datetime(today)
        day_end = fields.Datetime.add(day_start, days=1)
        customers = self.env["res.partner"].search([("sedar_is_customer_account", "=", True)])
        orders = self.env["sedar.marine.service.order"].search([("client_id", "in", customers.ids)])
        quotations = self.env["sedar.marketing.quotation"].search([("customer_id", "in", customers.ids)])
        contracts = self.env["sedar.marketing.contract"].search([("customer_id", "in", customers.ids)])
        appointments = self.env["calendar.event"].search([
            ("sedar_is_marketing_appointment", "=", True),
            ("sedar_customer_id", "in", customers.ids),
        ])
        upcoming = appointments.filtered(
            lambda item: item.start >= now and item.sedar_appointment_status not in {"completed", "cancelled", "no_show"}
        ).sorted("start")[:1]
        recent_activities = self.env["sedar.marketing.activity"].search(
            [("customer_id", "in", customers.ids)], limit=8
        )
        recent_notes = self.env["sedar.marketing.internal.note"].search(
            [("customer_id", "in", customers.ids)], limit=5
        )
        for dashboard in self:
            dashboard.service_request_count = len(orders)
            dashboard.pending_service_request_count = len(orders.filtered(
                lambda item: item.marketing_status not in {"completed", "cancelled"}
            ))
            dashboard.quotation_count = len(quotations)
            dashboard.pending_quotation_count = len(quotations.filtered(
                lambda item: item.status in {"internal_approval", "ready", "sent", "viewed"}
            ))
            dashboard.contract_count = len(contracts)
            dashboard.active_contract_count = len(contracts.filtered(lambda item: item.status == "active"))
            dashboard.completed_service_count = len(orders.filtered(
                lambda item: item.state in {"completed", "billing_ready", "closed"}
            ))
            dashboard.today_appointment_count = len(appointments.filtered(
                lambda item: day_start <= item.start < day_end
            ))
            dashboard.upcoming_appointment_id = upcoming
            dashboard.recent_activity_ids = recent_activities
            dashboard.recent_note_ids = recent_notes

    def action_open_customers(self):
        return self.env["ir.actions.actions"]._for_xml_id("sedar_marketing.action_sedar_marketing_customers")

    def action_open_service_requests(self):
        return self.env["ir.actions.actions"]._for_xml_id("sedar_marketing.action_sedar_marketing_service_requests")

    def action_open_quotations(self):
        return self.env["ir.actions.actions"]._for_xml_id("sedar_marketing.action_sedar_marketing_quotations")

    def action_open_contracts(self):
        return self.env["ir.actions.actions"]._for_xml_id("sedar_marketing.action_sedar_marketing_contracts")

    def action_open_appointments(self):
        return self.env["ir.actions.actions"]._for_xml_id("sedar_marketing.action_sedar_marketing_appointments")

    def action_new_service_request(self):
        action = self.action_open_service_requests()
        action.update({"view_mode": "form", "views": [(False, "form")], "target": "current"})
        return action

    def action_schedule_appointment(self):
        action = self.action_open_appointments()
        action.update({
            "view_mode": "form", "views": [(False, "form")], "target": "current",
            "context": {"default_sedar_is_marketing_appointment": True},
        })
        return action


class ResCompany(models.Model):
    _inherit = "res.company"

    def sedar_ensure_marketing_workspace(self):
        """Idempotently expose existing demo customers and roles in Marketing."""
        env = self.env
        company = self[:1] or env.company
        officer_group = env.ref("sedar_marketing.group_marketing_officer")
        manager_group = env.ref("sedar_marketing.group_marketing_manager")
        customer_relations = env.ref("sedar_marine_operations.group_customer_relations")
        commercial_managers = env.ref("sedar_marine_operations.group_commercial_manager")
        officers = env["res.users"].search([("group_ids", "in", customer_relations.id)])
        managers = env["res.users"].search([("group_ids", "in", commercial_managers.id)])
        admin = env.ref("base.user_admin", raise_if_not_found=False)
        officers.write({"group_ids": [(4, officer_group.id)]})
        (managers | admin).write({"group_ids": [(4, manager_group.id)]})

        orders = env["sedar.marine.service.order"].search([])
        for customer in orders.mapped("client_id.commercial_partner_id"):
            values = {"sedar_is_customer_account": True}
            if not customer.sedar_customer_code:
                values["sedar_customer_code"] = env["ir.sequence"].next_by_code("sedar.marketing.customer") or "New"
            if not customer.sedar_assigned_marketing_user_id:
                representative = orders.filtered(
                    lambda item: item.client_id.commercial_partner_id == customer
                ).mapped("marketing_representative_id")[:1]
                values["sedar_assigned_marketing_user_id"] = representative.id if representative else env.user.id
            contacts = customer.child_ids.filtered(lambda item: item.type == "contact")
            if not customer.sedar_primary_contact_id and contacts:
                values["sedar_primary_contact_id"] = contacts[0].id
            customer.with_context(sedar_skip_marketing_log=True).write(values)

        transaction_model = env["sedar.marketing.transaction"]
        for order in orders.filtered(lambda item: item.client_id.sedar_is_customer_account):
            transaction_model.sync_service_order(order)
            for invoice in order.invoice_ids:
                transaction_model.sync_invoice(invoice)
        return bool(company)

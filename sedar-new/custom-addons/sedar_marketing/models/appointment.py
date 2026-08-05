from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    sedar_is_marketing_appointment = fields.Boolean(string="SEDAR Marketing Appointment", index=True)
    sedar_customer_id = fields.Many2one("res.partner", string="Customer", index=True, ondelete="cascade", tracking=True)
    sedar_contact_id = fields.Many2one("res.partner", string="Customer Contact", ondelete="restrict", tracking=True)
    sedar_appointment_type = fields.Selection([
        ("client_meeting", "Client Meeting"), ("service_consultation", "Service Consultation"),
        ("site_inspection", "Site Inspection"), ("vessel_assessment", "Vessel Assessment"),
        ("quotation_discussion", "Quotation Discussion"), ("contract_discussion", "Contract Discussion"),
        ("follow_up", "Follow-up Call"), ("other", "Other"),
    ], tracking=True)
    sedar_appointment_status = fields.Selection([
        ("pending", "Pending Confirmation"), ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"), ("rescheduled", "Rescheduled"),
        ("completed", "Completed"), ("cancelled", "Cancelled"), ("no_show", "No Show"),
    ], default="scheduled", tracking=True, index=True)
    sedar_meeting_method = fields.Selection([
        ("in_person", "In Person"), ("phone", "Phone Call"), ("video", "Video Meeting")
    ], default="in_person", tracking=True)
    sedar_phone_number = fields.Char()
    sedar_alternative_phone = fields.Char()
    sedar_video_platform = fields.Selection([
        ("teams", "Microsoft Teams"), ("meet", "Google Meet"),
        ("zoom", "Zoom"), ("other", "Other"),
    ])
    sedar_meeting_link = fields.Char()
    sedar_service_order_id = fields.Many2one("sedar.marine.service.order", string="Service Request", ondelete="set null")
    sedar_quotation_id = fields.Many2one("sedar.marketing.quotation", ondelete="set null")
    sedar_contract_id = fields.Many2one("sedar.marketing.contract", ondelete="set null")
    sedar_agenda = fields.Text()
    sedar_customer_visible_notes = fields.Text()
    sedar_internal_notes = fields.Text()
    sedar_follow_up_required = fields.Boolean()
    sedar_follow_up_due_date = fields.Date()
    sedar_follow_up_completed = fields.Boolean()
    sedar_outcome = fields.Text()
    sedar_customer_response = fields.Text()
    sedar_next_action = fields.Char()
    sedar_no_show_party = fields.Selection([
        ("customer", "Customer"), ("sedar", "SEDAR Representative"), ("both", "Both")
    ])
    sedar_status_history_ids = fields.One2many(
        "sedar.marketing.appointment.status", "appointment_id", string="Status History", readonly=True
    )

    @api.constrains("sedar_customer_id", "sedar_contact_id")
    def _check_sedar_contact_customer(self):
        for appointment in self.filtered("sedar_is_marketing_appointment"):
            if not appointment.sedar_customer_id or not appointment.sedar_contact_id:
                raise ValidationError("Marketing appointments require a customer and contact.")
            if appointment.sedar_contact_id.commercial_partner_id != appointment.sedar_customer_id.commercial_partner_id:
                raise ValidationError("The appointment contact must belong to the customer.")

    @api.model_create_multi
    def create(self, vals_list):
        appointments = super().create(vals_list)
        for appointment in appointments.filtered("sedar_is_marketing_appointment"):
            self.env["sedar.marketing.appointment.status"].sudo().create({
                "appointment_id": appointment.id,
                "to_status": appointment.sedar_appointment_status,
                "changed_by_id": self.env.user.id,
            })
            self.env["sedar.marketing.activity"].log(
                appointment.sedar_customer_id, "appointments", "created",
                f"Appointment {appointment.name} created.", appointment,
            )
        return appointments

    def write(self, vals):
        before = {
            item.id: {
                "status": item.sedar_appointment_status,
                "start": item.start,
                "stop": item.stop,
            }
            for item in self.filtered("sedar_is_marketing_appointment")
        }
        result = super().write(vals)
        if self.env.context.get("sedar_skip_appointment_log"):
            return result
        for appointment in self.filtered("sedar_is_marketing_appointment"):
            old = before.get(appointment.id)
            if not old:
                continue
            if "sedar_appointment_status" in vals and old["status"] != appointment.sedar_appointment_status:
                self.env["sedar.marketing.appointment.status"].sudo().create({
                    "appointment_id": appointment.id,
                    "from_status": old["status"],
                    "to_status": appointment.sedar_appointment_status,
                    "changed_by_id": self.env.user.id,
                    "previous_start": old["start"], "previous_stop": old["stop"],
                })
                self.env["sedar.marketing.activity"].log(
                    appointment.sedar_customer_id, "appointments", "status_changed",
                    f"Appointment {appointment.name} changed status.", appointment,
                    [("status", old["status"], appointment.sedar_appointment_status)],
                )
            elif vals:
                self.env["sedar.marketing.activity"].log(
                    appointment.sedar_customer_id, "appointments", "updated",
                    f"Appointment {appointment.name} updated.", appointment,
                )
        return result

    def action_sedar_confirm(self):
        self._sedar_require_status("pending", "scheduled", "rescheduled")
        self.write({"sedar_appointment_status": "confirmed"})

    def action_sedar_reschedule(self):
        self._sedar_require_status("pending", "scheduled", "confirmed")
        self.write({"sedar_appointment_status": "rescheduled"})

    def action_sedar_complete(self):
        self._sedar_require_status("scheduled", "confirmed", "rescheduled")
        if any(not item.sedar_outcome for item in self):
            raise UserError("An appointment outcome is required before completion.")
        if any(item.sedar_follow_up_required and not item.sedar_follow_up_due_date for item in self):
            raise UserError("A follow-up due date is required when follow-up is selected.")
        self.write({"sedar_appointment_status": "completed"})

    def action_sedar_cancel(self):
        self._sedar_require_status("pending", "scheduled", "confirmed", "rescheduled")
        self.write({"sedar_appointment_status": "cancelled"})

    def action_sedar_no_show(self):
        self._sedar_require_status("scheduled", "confirmed", "rescheduled")
        if any(not item.sedar_no_show_party for item in self):
            raise UserError("Identify who did not attend before marking No Show.")
        self.write({"sedar_appointment_status": "no_show"})

    def action_sedar_complete_follow_up(self):
        if any(not item.sedar_follow_up_required for item in self):
            raise UserError("This appointment has no required follow-up.")
        self.write({"sedar_follow_up_completed": True})
        for appointment in self:
            self.env["sedar.marketing.activity"].log(
                appointment.sedar_customer_id, "appointments", "followup_completed",
                f"Follow-up completed for {appointment.name}.", appointment,
            )

    def _sedar_require_status(self, *allowed):
        if any(item.sedar_appointment_status not in allowed for item in self):
            raise UserError(f"This action requires appointment status: {', '.join(allowed)}.")


class SedarMarketingAppointmentStatus(models.Model):
    _name = "sedar.marketing.appointment.status"
    _description = "SEDAR Marketing Appointment Status History"
    _order = "occurred_at desc, id desc"

    appointment_id = fields.Many2one("calendar.event", required=True, ondelete="cascade", index=True)
    from_status = fields.Selection([
        ("pending", "Pending Confirmation"), ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"), ("rescheduled", "Rescheduled"),
        ("completed", "Completed"), ("cancelled", "Cancelled"), ("no_show", "No Show"),
    ], string="Previous Status", readonly=True)
    to_status = fields.Selection([
        ("pending", "Pending Confirmation"), ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"), ("rescheduled", "Rescheduled"),
        ("completed", "Completed"), ("cancelled", "Cancelled"), ("no_show", "No Show"),
    ], required=True)
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    changed_by_id = fields.Many2one("res.users", readonly=True, ondelete="set null")
    reason = fields.Char()
    notes = fields.Text()
    previous_start = fields.Datetime(readonly=True)
    previous_stop = fields.Datetime(readonly=True)

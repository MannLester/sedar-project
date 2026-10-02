"""Repeatable reconciliation for the Marketing workspace and fictional demo."""

from datetime import datetime


MODULE = "sedar_marketing"


def _record(env, model, xmlid, values, *, update=True):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid),
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            if update:
                record.with_context(
                    sedar_skip_appointment_log=True,
                    sedar_skip_contract_log=True,
                    sedar_skip_document_log=True,
                    sedar_skip_marketing_log=True,
                    sedar_skip_quotation_log=True,
                ).write(values)
            return record
        data.unlink()
    record = env[model].create(values)
    env["ir.model.data"].create({
        "module": MODULE,
        "name": xmlid,
        "model": model,
        "res_id": record.id,
        "noupdate": True,
    })
    return record


def post_init_hook(env):
    env.company.sedar_ensure_marketing_workspace()
    ensure_marketing_demo(env)
    return True


def ensure_marketing_demo(env):
    """Create a connected, fictional Marketing story when demo orders exist."""
    completed_order = env.ref(
        "sedar_service_order_demo.order_completed", raise_if_not_found=False,
    )
    ready_order = env.ref(
        "sedar_service_order_demo.order_ready", raise_if_not_found=False,
    )
    if not completed_order or not ready_order:
        return False

    approved_quotation = _record(env, "sedar.marketing.quotation", "demo_quotation_approved", {
        "service_order_id": completed_order.id,
        "customer_id": completed_order.client_id.id,
        "contact_id": completed_order.contact_id.id,
        "subject": f"Completed harbor assistance for {completed_order.assisted_vessel_name}",
        "status": "customer_approved",
        "issued_at": datetime(2026, 7, 20, 9),
        "response_type": "approved",
        "response_contact_id": completed_order.contact_id.id,
        "response_date": datetime(2026, 7, 22, 14),
        "terms_and_conditions": "Thirty-day payment terms; fictional demonstration record.",
        "terms_reference": "DEMO-STANDARD-MARINE-SERVICES",
    })
    _record(env, "sedar.marketing.quotation.line", "demo_quotation_approved_line", {
        "quotation_id": approved_quotation.id,
        "description": "Harbor tug assistance",
        "quantity": 3.0,
        "unit_price": 5250.0,
        "tax_rate": 12.0,
    })

    pending_quotation = _record(env, "sedar.marketing.quotation", "demo_quotation_pending", {
        "service_order_id": ready_order.id,
        "customer_id": ready_order.client_id.id,
        "contact_id": ready_order.contact_id.id,
        "subject": f"Planned harbor assistance for {ready_order.assisted_vessel_name}",
        "status": "sent",
        "issued_at": datetime(2026, 8, 5, 10),
        "sent_at": datetime(2026, 8, 5, 10),
        "terms_and_conditions": "Valid for thirty days; fictional demonstration record.",
        "terms_reference": "DEMO-STANDARD-MARINE-SERVICES",
    })
    _record(env, "sedar.marketing.quotation.line", "demo_quotation_pending_line", {
        "quotation_id": pending_quotation.id,
        "description": "High-power tug assistance",
        "quantity": 3.0,
        "unit_price": 19500.0,
        "tax_rate": 12.0,
    })

    contract = _record(env, "sedar.marketing.contract", "demo_contract_active", {
        "title": f"Harbor Assistance Agreement — {completed_order.assisted_vessel_name}",
        "customer_id": completed_order.client_id.id,
        "contact_id": completed_order.contact_id.id,
        "quotation_id": approved_quotation.id,
        "service_order_id": completed_order.id,
        "service_type_id": completed_order.service_type_id.id,
        "vessel_name": completed_order.assisted_vessel_name,
        "effective_date": "2026-07-23",
        "expiration_date": "2027-07-22",
        "contract_value": approved_quotation.amount_total,
        "currency_id": approved_quotation.currency_id.id,
        "status": "active",
        "selected_customer_contact_id": completed_order.contact_id.id,
        "fully_executed_at": datetime(2026, 7, 23, 11),
        "terms_and_conditions": "Executed fictional agreement for demonstration purposes.",
    })
    _record(env, "sedar.marketing.contract.signature", "demo_contract_signature_sedar", {
        "contract_id": contract.id,
        "party": "sedar",
        "signatory_name": "Demo SEDAR President",
        "organization": "SEDAR Tug and Barge Services Corporation",
        "position": "President",
        "signed_at": datetime(2026, 7, 23, 9),
        "supporting_document_name": "demo-contract-signature-evidence.pdf",
        "verification_status": "verified",
    })
    _record(env, "sedar.marketing.contract.signature", "demo_contract_signature_customer", {
        "contract_id": contract.id,
        "party": "customer",
        "signatory_name": completed_order.contact_id.name,
        "organization": completed_order.client_id.name,
        "position": "Authorized Representative",
        "signed_at": datetime(2026, 7, 23, 10),
        "supporting_document_name": "demo-customer-signature-evidence.pdf",
        "verification_status": "verified",
    })

    appointment = _record(env, "calendar.event", "demo_appointment_upcoming", {
        "name": f"Pre-service coordination — {ready_order.assisted_vessel_name}",
        "start": datetime(2026, 8, 20, 9),
        "stop": datetime(2026, 8, 20, 10),
        "sedar_is_marketing_appointment": True,
        "sedar_customer_id": ready_order.client_id.id,
        "sedar_contact_id": ready_order.contact_id.id,
        "sedar_appointment_type": "service_consultation",
        "sedar_appointment_status": "confirmed",
        "sedar_meeting_method": "video",
        "sedar_video_platform": "teams",
        "sedar_meeting_link": "https://teams.example.test/sedar-demo-coordination",
        "sedar_service_order_id": ready_order.id,
        "sedar_quotation_id": pending_quotation.id,
        "sedar_agenda": "Confirm tug window, berth readiness, and customer contacts.",
        "sedar_follow_up_required": True,
        "sedar_follow_up_due_date": "2026-08-21",
    })

    document = _record(env, "sedar.marketing.document", "demo_document_capability_brief", {
        "customer_id": ready_order.client_id.id,
        "title": "SEDAR Harbor Assistance Capability Brief",
        "description": "Fictional file metadata used to demonstrate customer document tracking.",
        "document_type": "marketing_material",
        "department": "marketing",
        "visibility": "shared",
        "source": "uploaded",
        "status": "active",
        "linked_service_order_id": ready_order.id,
        "linked_quotation_id": pending_quotation.id,
        "linked_appointment_id": appointment.id,
    })
    _record(env, "sedar.marketing.document.version", "demo_document_capability_brief_v1", {
        "document_id": document.id,
        "filename": "sedar-harbor-assistance-capability-demo.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 245760,
        "notes": "Metadata only; no file bytes are stored in this demonstration.",
    }, update=False)
    _record(env, "sedar.marketing.document.request", "demo_document_request_pending", {
        "customer_id": ready_order.client_id.id,
        "title": "Updated vessel particulars",
        "document_type": "certificate",
        "description": "Request updated vessel particulars before the scheduled service.",
        "department": "operations",
        "due_date": "2026-08-18",
        "status": "pending",
    })
    _record(env, "sedar.marketing.internal.note", "demo_internal_note", {
        "customer_id": ready_order.client_id.id,
        "note": "Customer prefers a coordination call before final tug dispatch confirmation.",
    })
    return True

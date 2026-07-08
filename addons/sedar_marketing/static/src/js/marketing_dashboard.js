/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_META = {
    pending_review: { label: "Pending Review", className: "is-gray", title: "Ops is reviewing feasibility." },
    drafting_quote: { label: "Drafting Quote", className: "is-blue", title: "Ops is calculating costs." },
    pending_approval: { label: "Pending Approval", className: "is-yellow", title: "Waiting for client to say yes/no." },
    for_signature: { label: "For Signature", className: "is-orange", title: "Waiting for the formal contract to be signed." },
    scheduled: { label: "Scheduled", className: "is-green", title: "Handed over to dispatch." },
    completed: { label: "Completed", className: "is-purple", title: "Job done." },
    cancelled: { label: "Cancelled", className: "is-red", title: "Job dead." },
};

const ACTIVE_STATUSES = ["pending_review", "drafting_quote", "pending_approval", "for_signature", "scheduled", "completed", "cancelled"];

const SERVICE_LABELS = {
    ship_assist: "Ship Assist",
    barge_tow: "Barge Towage",
    escort: "Escort",
    standby: "Standby",
    emergency: "Emergency Assist",
    terminal: "Terminal Support",
};

const SCHEDULE = [
    { time: "09:00", type: "Client Meeting", className: "is-meeting", title: "Discuss Harbor Towage Requireme...", customer: "Maersk Philippines" },
    { time: "12:00", type: "Site Visit", className: "is-site", title: "Service Discussion for MT Ocean Tr...", customer: "NYK Line" },
    { time: "14:30", type: "Client Meeting", className: "is-meeting", title: "Fleet Expansion Sync", customer: "Evergreen Marine" },
    { time: "16:00", type: "Contract Signing", className: "is-contract", title: "Contract Renewal", customer: "AGS Philippines" },
];

export class SedarMarketingDashboard extends Component {
    static template = "sedar_marketing.MarketingDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.schedule = SCHEDULE;
        this.state = useState({ requests: [], kpis: this.buildKpis([]) });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const records = await this.orm.searchRead(
            "sedar.marketing.record",
            [["status", "in", ACTIVE_STATUSES]],
            ["id", "company_name", "vessel_name", "service_type", "purpose_of_request", "status", "priority_level", "next_action_date"],
            { order: "id desc", limit: 50 }
        );
        this.state.requests = records.map((record) => ({
            ref: `REQ-${String(record.id).padStart(4, "0")}`,
            customer: record.company_name || "Unnamed Customer",
            vessel: record.vessel_name || "No vessel name yet",
            service: SERVICE_LABELS[record.service_type] || record.service_type || record.purpose_of_request || "Service not set",
            status: record.status || "pending_review",
            priority: record.priority_level || "normal",
        }));
        this.state.kpis = this.buildKpis(this.state.requests);
    }

    buildKpis(requests) {
        const urgentCount = requests.filter((request) => ["urgent", "emergency"].includes(request.priority)).length;
        return [
            { label: "Pending Request", value: requests.filter((request) => request.status === "pending_review").length, note: `${urgentCount} Urgent`, icon: "fa-file-text" },
            { label: "Customer Approval", value: requests.filter((request) => request.status === "pending_approval").length, note: "", icon: "fa-clock-o" },
            { label: "Pending Contracts", value: requests.filter((request) => request.status === "for_signature").length, note: "", icon: "fa-file-text-o" },
            { label: "Today’s Schedule", value: this.schedule.length, note: "", icon: "fa-calendar" },
        ];
    }

    statusMeta(status) {
        return STATUS_META[status] || STATUS_META.pending_review;
    }

    openNewServiceRequest() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Service Request",
            res_model: "sedar.marketing.record",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_name: "New Service Request",
                default_flow_step: "customer",
                default_record_type: "customer_pipeline",
                default_status: "new",
            },
        });
    }

    openRequests() {
        this.action.doAction("sedar_marketing.action_sedar_marketing_record");
    }
}

registry.category("actions").add("sedar_marketing_dashboard", SedarMarketingDashboard);

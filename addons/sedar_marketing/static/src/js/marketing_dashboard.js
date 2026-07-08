/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_META = {
    draft: { label: "Draft", className: "is-draft", title: "Saved but not submitted yet." },
    pending_review: { label: "Pending Review", className: "is-gray", title: "Ops is reviewing feasibility." },
    drafting_quote: { label: "Drafting Quote", className: "is-blue", title: "Ops is calculating costs." },
    pending_approval: { label: "Pending Approval", className: "is-yellow", title: "Waiting for client to say yes/no." },
    for_signature: { label: "For Signature", className: "is-orange", title: "Waiting for the formal contract to be signed." },
    scheduled: { label: "Scheduled", className: "is-green", title: "Handed over to dispatch." },
    completed: { label: "Completed", className: "is-purple", title: "Job done." },
    cancelled: { label: "Cancelled", className: "is-red", title: "Job dead." },
};

const ACTIVE_STATUSES = ["pending_review", "drafting_quote", "pending_approval", "for_signature", "scheduled", "completed", "cancelled"];
const DASHBOARD_STATUSES = ["draft", ...ACTIVE_STATUSES];

const REQUEST_FILTERS = [
    { key: "all", label: "All" },
    { key: "active", label: "Active" },
    { key: "draft", label: "Drafts" },
];

const SERVICE_LABELS = {
    ship_assist: "Ship Assist",
    barge_tow: "Barge Towage",
    escort: "Escort",
    standby: "Standby",
    emergency: "Emergency Assist",
    terminal: "Terminal Support",
};

const APPOINTMENT_META = {
    client_meeting: { label: "Client Meeting", className: "is-meeting" },
    site_visit: { label: "Site Visit", className: "is-site" },
    contract_signing: { label: "Contract Signing", className: "is-contract" },
    follow_up: { label: "Follow-up", className: "is-follow-up" },
};

export class SedarMarketingDashboard extends Component {
    static template = "sedar_marketing.MarketingDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ requests: [], schedule: [], kpis: this.buildKpis([], []), requestFilter: "all" });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const records = await this.orm.searchRead(
            "sedar.marketing.record",
            [["status", "in", DASHBOARD_STATUSES]],
            ["id", "company_name", "vessel_name", "service_type", "purpose_of_request", "status", "priority_level", "next_action_date"],
            { order: "id desc", limit: 50 }
        );
        const today = new Date().toISOString().slice(0, 10);
        const appointments = await this.orm.searchRead(
            "sedar.marketing.appointment",
            [["start_datetime", ">=", `${today} 00:00:00`], ["start_datetime", "<=", `${today} 23:59:59`]],
            ["name", "company_name", "appointment_type", "start_datetime"],
            { order: "start_datetime", limit: 8 }
        );
        this.state.requests = records.map((record) => ({
            id: record.id,
            ref: `REQ-${String(record.id).padStart(4, "0")}`,
            customer: record.company_name || "Unnamed draft",
            vessel: record.vessel_name || "No vessel name yet",
            service: SERVICE_LABELS[record.service_type] || record.service_type || record.purpose_of_request || "Service not set",
            status: record.status || "pending_review",
            priority: record.priority_level || "normal",
        }));
        this.state.schedule = appointments.map((appointment) => {
            const meta = APPOINTMENT_META[appointment.appointment_type] || APPOINTMENT_META.client_meeting;
            return {
                time: this.formatTime(appointment.start_datetime),
                type: meta.label,
                className: meta.className,
                title: appointment.name || "Marketing appointment",
                customer: appointment.company_name || "No customer set",
            };
        });
        this.state.kpis = this.buildKpis(this.activeRequests, this.state.schedule);
    }

    get requestFilters() {
        return REQUEST_FILTERS;
    }

    get activeRequests() {
        return this.state.requests.filter((request) => request.status !== "draft");
    }

    get filteredRequests() {
        if (this.state.requestFilter === "draft") {
            return this.state.requests.filter((request) => request.status === "draft");
        }
        if (this.state.requestFilter === "active") {
            return this.activeRequests;
        }
        return this.state.requests;
    }

    get requestPanelTitle() {
        return this.state.requestFilter === "draft" ? "Saved Drafts" : "Service Requests";
    }

    get emptyRequestMessage() {
        return this.state.requestFilter === "draft" ? "No saved drafts yet." : "No service requests found.";
    }

    buildKpis(requests, schedule) {
        const urgentCount = requests.filter((request) => ["urgent", "emergency"].includes(request.priority)).length;
        return [
            { label: "Pending Request", value: requests.filter((request) => request.status === "pending_review").length, note: `${urgentCount} Urgent`, icon: "fa-file-text" },
            { label: "Customer Approval", value: requests.filter((request) => request.status === "pending_approval").length, note: "", icon: "fa-clock-o" },
            { label: "Pending Contracts", value: requests.filter((request) => request.status === "for_signature").length, note: "", icon: "fa-file-text-o" },
            { label: "Today’s Schedule", value: schedule.length, note: "", icon: "fa-calendar" },
        ];
    }

    formatTime(value) {
        if (!value) {
            return "--:--";
        }
        const date = new Date(`${value.replace(" ", "T")}Z`);
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    }

    statusMeta(status) {
        return STATUS_META[status] || STATUS_META.pending_review;
    }

    setRequestFilter(ev) {
        this.state.requestFilter = ev.currentTarget.dataset.filter;
    }

    requestFilterClass(filterKey) {
        return `o_sedar_filter_button${this.state.requestFilter === filterKey ? " is-active" : ""}`;
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

    openRequest(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sedar.marketing.record",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openCalendar() {
        this.action.doAction("sedar_marketing.action_sedar_marketing_appointment");
    }
}

registry.category("actions").add("sedar_marketing_dashboard", SedarMarketingDashboard);

export class SedarMarketingDraftsBoard extends Component {
    static template = "sedar_marketing.MarketingDraftsBoard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ drafts: [] });

        onWillStart(async () => {
            await this.loadDrafts();
        });
    }

    async loadDrafts() {
        const records = await this.orm.searchRead(
            "sedar.marketing.record",
            [["status", "=", "draft"]],
            ["id", "name", "flow_step", "company_name", "contact_person", "communication_method", "service_type", "purpose_of_request", "write_date"],
            { order: "write_date desc, id desc", limit: 80 }
        );
        this.state.drafts = records.map((record) => ({
            ...record,
            ref: `REQ-${String(record.id).padStart(4, "0")}`,
            customer: record.company_name || "Unnamed draft",
            contact: record.contact_person || "No contact yet",
            stepLabel: this.formatStep(record.flow_step),
            service: SERVICE_LABELS[record.service_type] || record.purpose_of_request || "Service not set",
            updated: this.formatDate(record.write_date),
        }));
    }

    formatStep(value) {
        return { customer: "Customer", requirements: "Requirements", vessel_info: "Vessel Info", review: "Review" }[value] || "Customer";
    }

    formatDate(value) {
        if (!value) {
            return "No date";
        }
        return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
    }

    openDraft(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sedar.marketing.record",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openDashboard() {
        this.action.doAction("sedar_marketing.action_sedar_marketing_dashboard");
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
}

registry.category("actions").add("sedar_marketing_drafts_board", SedarMarketingDraftsBoard);

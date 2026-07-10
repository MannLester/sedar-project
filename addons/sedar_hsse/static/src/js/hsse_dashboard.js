/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DASHBOARD = {
    eyebrow: "HSSE Control",
    title: "Safety Events",
    subtitle: "Report, review, investigate, and close every safety event from one register.",
    checklist: ["Capture the event facts and evidence", "Classify and investigate when required", "Complete risk controls before closure"],
};

const STATUS_META = {
    open: { label: "Submitted", className: "is-submitted" },
    review: { label: "Under Review", className: "is-review" },
    investigating: { label: "Investigating", className: "is-investigating" },
    closed: { label: "Closed", className: "is-closed" },
};

const CLASSIFICATION_LABELS = {
    observation: "Observation",
    near_miss: "Near Miss",
    minor: "Minor",
    major: "Major",
    reportable: "Reportable",
};

export class SedarHsseDashboard extends Component {
    static template = "sedar_hsse.HsseStageDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.config = DASHBOARD;
        this.state = useState({ records: [], activeState: null, loading: true });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        const fields = ["id", "name", "date", "vessel_id", "location", "classification", "state", "reported_by_id"];
        const records = await this.orm.searchRead("sedar.hsse.incident", [], fields, { order: "date desc, id desc", limit: 200 });
        this.state.records = records.map((record) => this.normalize(record));
        this.state.loading = false;
    }

    normalize(record) {
        return {
            ...record,
            reference: `SE-${String(record.id).padStart(4, "0")}`,
            vessel: Array.isArray(record.vessel_id) ? record.vessel_id[1] : "No vessel set",
            reporter: Array.isArray(record.reported_by_id) ? record.reported_by_id[1] : "Reporter not set",
            classificationLabel: CLASSIFICATION_LABELS[record.classification] || "Unclassified",
        };
    }

    get visibleRecords() {
        if (!this.state.activeState) {
            return this.state.records;
        }
        return this.state.records.filter((record) => record.state === this.state.activeState);
    }

    get queueTitle() {
        return this.state.activeState ? `${STATUS_META[this.state.activeState].label} Events` : "All Safety Events";
    }

    get emptyMessage() {
        return this.state.activeState ? `No ${STATUS_META[this.state.activeState].label.toLowerCase()} safety events.` : "No safety events have been submitted yet.";
    }

    get kpis() {
        const records = this.state.records;
        return [
            { state: "open", label: "Submitted", value: records.filter((item) => item.state === "open").length, note: "new reports", icon: "fa-paper-plane" },
            { state: "review", label: "Under Review", value: records.filter((item) => item.state === "review").length, note: "HSSE triage", icon: "fa-search" },
            { state: "investigating", label: "Investigating", value: records.filter((item) => item.state === "investigating").length, note: "serious events", icon: "fa-shield" },
            { state: "closed", label: "Closed", value: records.filter((item) => item.state === "closed").length, note: "completed records", icon: "fa-check-circle" },
        ];
    }

    filterByState(ev) {
        const selectedState = ev.currentTarget.dataset.state;
        this.state.activeState = this.state.activeState === selectedState ? null : selectedState;
    }

    statusMeta(state) {
        return STATUS_META[state] || STATUS_META.open;
    }

    classificationClass(classification) {
        return `o_hsse_classification is-${classification || "unclassified"}`;
    }

    openRecord(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sedar.hsse.incident",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createEvent() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Safety Event",
            res_model: "sedar.hsse.incident",
            views: [[false, "form"]],
            target: "current",
        });
    }

    refresh() {
        return this.loadDashboard();
    }
}

registry.category("actions").add("sedar_hsse_event_reports_dashboard", SedarHsseDashboard);

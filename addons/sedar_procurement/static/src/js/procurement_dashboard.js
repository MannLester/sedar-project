/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_LABELS = {
    draft: "Request",
    pending_approval: "Approval",
    approved: "PO Draft",
    ordered: "Ordered",
    received: "Delivered",
};

const PERFORMANCE_META = {
    good: { label: "On Track", className: "is-good" },
    watch: { label: "Watch", className: "is-watch" },
    risk: { label: "Risk", className: "is-risk" },
};

export class SedarProcurementDashboard extends Component {
    static template = "sedar_procurement.ProcurementDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ records: [], inventory: [], kpis: [], flow: [], actions: [], delivery: [] });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const records = await this.orm.searchRead(
            "sedar.procurement.record",
            [],
            ["id", "name", "record_type", "supplier", "requested_by", "request_date", "amount", "expected_delivery", "approval_age_days", "supplier_lead_days", "delivery_performance", "status", "approval_owner"],
            { order: "request_date desc, id desc", limit: 40 }
        );
        const inventory = await this.orm.searchRead(
            "sedar.inventory.item",
            [["status", "in", ["low", "critical"]]],
            ["id", "name", "warehouse", "quantity_on_hand", "reorder_point", "status", "procurement_signal"],
            { order: "status, name", limit: 8 }
        );
        this.state.records = records.map((record) => this.normalizeRecord(record));
        this.state.inventory = inventory;
        this.state.kpis = this.buildKpis(this.state.records, inventory);
        this.state.flow = this.buildFlow(this.state.records);
        this.state.actions = this.buildActions(this.state.records, inventory);
        this.state.delivery = this.buildDelivery(this.state.records);
    }

    normalizeRecord(record) {
        const performance = PERFORMANCE_META[record.delivery_performance] || PERFORMANCE_META.good;
        return {
            ...record,
            ref: record.name?.split(" ")[0] || `PR-${record.id}`,
            title: record.name?.replace(/^\S+\s*/, "") || "Procurement item",
            statusLabel: STATUS_LABELS[record.status] || "Request",
            typeLabel: { pr: "PR", rfq: "RFQ", po: "PO" }[record.record_type] || "PR",
            performanceLabel: performance.label,
            performanceClass: performance.className,
            typeClass: `type-${record.record_type || "pr"}`,
            amountLabel: this.formatCurrency(record.amount),
            dateLabel: record.expected_delivery ? `Due ${this.formatShortDate(record.expected_delivery)}` : record.request_date ? `Opened ${this.formatShortDate(record.request_date)}` : "No date",
        };
    }

    buildKpis(records, inventory) {
        return [
            { label: "Pending PRs", value: records.filter((record) => record.record_type === "pr" && record.status !== "received").length, note: `${inventory.length} low-stock signals`, icon: "fa-clipboard" },
            { label: "RFQs / Canvass", value: records.filter((record) => record.status === "draft").length, note: "ready for supplier scan", icon: "fa-send" },
            { label: "For Approval", value: records.filter((record) => record.status === "pending_approval").length, note: "needs sign-off", icon: "fa-check-square-o" },
            { label: "Late / Risk", value: records.filter((record) => record.delivery_performance === "risk" || record.approval_age_days > 5).length, note: "supplier watchlist", icon: "fa-exclamation-triangle" },
        ];
    }

    buildFlow(records) {
        const columns = [
            { key: "draft", label: "Request", items: [] },
            { key: "pending_approval", label: "Approval", items: [] },
            { key: "approved", label: "PO Draft", items: [] },
            { key: "ordered", label: "Ordered", items: [] },
            { key: "received", label: "Delivered", items: [] },
        ];
        const byKey = Object.fromEntries(columns.map((column) => [column.key, column]));
        for (const record of records.slice(0, 12)) {
            (byKey[record.status] || byKey.draft).items.push(record);
        }
        return columns;
    }

    buildActions(records, inventory) {
        const actions = [];
        for (const item of inventory.slice(0, 3)) {
            actions.push({ label: item.status === "critical" ? "Critical stock" : "Low stock", title: item.name, detail: item.procurement_signal || `${item.quantity_on_hand}/${item.reorder_point} remaining` });
        }
        for (const record of records.filter((item) => item.status === "pending_approval" || item.delivery_performance !== "good").slice(0, 4)) {
            actions.push({ label: record.statusLabel, title: record.title, detail: record.approval_owner || record.supplier || "Assign owner" });
        }
        return actions.slice(0, 6);
    }

    buildDelivery(records) {
        return records
            .filter((record) => record.expected_delivery)
            .sort((a, b) => a.expected_delivery.localeCompare(b.expected_delivery))
            .slice(0, 5);
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP", maximumFractionDigits: 0 }).format(value || 0);
    }

    formatShortDate(value) {
        return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
    }

    openRecords() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_records_board");
    }

    openRecord(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sedar.procurement.record",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openNewPurchaseRequest() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_new_request");
    }

    openSendRfq() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_send_rfq");
    }

    openCreatePo() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_create_po");
    }
}

registry.category("actions").add("sedar_procurement_dashboard", SedarProcurementDashboard);

export class SedarProcurementRecordsBoard extends Component {
    static template = "sedar_procurement.ProcurementRecordsBoard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ records: [], activeType: "all" });

        onWillStart(async () => {
            await this.loadRecords();
        });
    }

    async loadRecords() {
        const records = await this.orm.searchRead(
            "sedar.procurement.record",
            [],
            ["id", "name", "record_type", "supplier", "requested_by", "request_date", "amount", "expected_delivery", "approval_age_days", "supplier_lead_days", "delivery_performance", "status", "approval_owner", "item_name", "quantity", "unit_of_measure"],
            { order: "request_date desc, id desc", limit: 80 }
        );
        this.state.records = records.map((record) => this.normalizeRecord(record));
    }

    normalizeRecord(record) {
        const performance = PERFORMANCE_META[record.delivery_performance] || PERFORMANCE_META.good;
        return {
            ...record,
            ref: record.name?.split(" ")[0] || `PR-${record.id}`,
            title: record.name?.replace(/^\S+\s*/, "") || "Procurement item",
            statusLabel: STATUS_LABELS[record.status] || "Request",
            typeLabel: { pr: "Purchase Request", rfq: "RFQ", po: "Purchase Order" }[record.record_type] || "Request",
            performanceLabel: performance.label,
            performanceClass: performance.className,
            amountLabel: this.formatCurrency(record.amount),
            dateLabel: this.formatDate(record.request_date),
            deliveryLabel: this.formatDate(record.expected_delivery),
        };
    }

    get filteredRecords() {
        if (this.state.activeType === "all") {
            return this.state.records;
        }
        return this.state.records.filter((record) => record.record_type === this.state.activeType);
    }

    get summary() {
        const records = this.state.records;
        return {
            total: records.length,
            pr: records.filter((record) => record.record_type === "pr").length,
            rfq: records.filter((record) => record.record_type === "rfq").length,
            po: records.filter((record) => record.record_type === "po").length,
        };
    }

    setType(ev) {
        this.state.activeType = ev.currentTarget.dataset.type;
    }

    openDashboard() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_dashboard");
    }

    openRecord(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sedar.procurement.record",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openNewPurchaseRequest() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_new_request");
    }

    openSendRfq() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_send_rfq");
    }

    openCreatePo() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_create_po");
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP", maximumFractionDigits: 0 }).format(value || 0);
    }

    formatDate(value) {
        if (!value) {
            return "No date";
        }
        return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
    }
}

registry.category("actions").add("sedar_procurement_records_board", SedarProcurementRecordsBoard);

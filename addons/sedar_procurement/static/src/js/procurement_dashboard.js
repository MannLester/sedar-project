/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_LABELS = {
    draft: "RFQ",
    sent: "RFQ Sent",
    to_approve: "Approval",
    purchase: "Purchase Order",
    done: "Locked",
    cancel: "Cancelled",
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
        this.flowFormViewId = null;
        this.state = useState({ records: [], inventory: [], kpis: [], flow: [], actions: [], delivery: [] });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const records = await this.orm.searchRead(
            "purchase.order",
            [],
            ["id", "name", "partner_id", "user_id", "date_order", "date_planned", "amount_total", "state", "sedar_budget_amount", "sedar_over_budget", "sedar_canvassing_required", "sedar_canvassing_done", "sedar_urgent_exception", "sedar_quote_count"],
            { order: "date_order desc, id desc", limit: 40 }
        );
        const inventory = await this.orm.searchRead(
            "product.product",
            [["purchase_ok", "=", true]],
            ["id", "name", "default_code", "qty_available", "virtual_available", "sedar_tug_use", "sedar_vessel_id", "sedar_item_size", "sedar_critical_part"],
            { order: "name", limit: 8 }
        );
        this.state.records = records.map((record) => this.normalizeRecord(record));
        this.state.inventory = inventory;
        this.state.kpis = this.buildKpis(this.state.records, inventory);
        this.state.flow = this.buildFlow(this.state.records);
        this.state.actions = this.buildActions(this.state.records, inventory);
        this.state.delivery = this.buildDelivery(this.state.records);
    }

    normalizeRecord(record) {
        const performance = this.getPerformance(record);
        const partner = Array.isArray(record.partner_id) ? record.partner_id[1] : "Supplier not set";
        const requester = Array.isArray(record.user_id) ? record.user_id[1] : "Owner not set";
        return {
            ...record,
            ref: record.name || `PO-${record.id}`,
            title: partner,
            supplier: partner,
            requested_by: requester,
            status: record.state,
            statusLabel: STATUS_LABELS[record.state] || "RFQ",
            typeLabel: record.state === "purchase" || record.state === "done" ? "PO" : "RFQ",
            performanceLabel: performance.label,
            performanceClass: performance.className,
            typeClass: record.state === "purchase" || record.state === "done" ? "type-po" : "type-rfq",
            amountLabel: this.formatCurrency(record.amount_total),
            expected_delivery: record.date_planned,
            approval_age_days: this.getAgeDays(record.date_order),
            supplier_lead_days: 0,
            delivery_performance: performance.key,
            dateLabel: record.date_planned ? `Due ${this.formatShortDate(record.date_planned)}` : record.date_order ? `Opened ${this.formatShortDate(record.date_order)}` : "No date",
        };
    }

    getPerformance(record) {
        if (record.sedar_over_budget || record.sedar_canvassing_required) {
            return { ...PERFORMANCE_META.risk, key: "risk" };
        }
        if (record.state === "to_approve" || record.sedar_urgent_exception) {
            return { ...PERFORMANCE_META.watch, key: "watch" };
        }
        return { ...PERFORMANCE_META.good, key: "good" };
    }

    getAgeDays(value) {
        if (!value) {
            return 0;
        }
        return Math.floor((Date.now() - new Date(value).getTime()) / 86400000);
    }

    buildKpis(records, inventory) {
        return [
            { label: "Open RFQs", value: records.filter((record) => ["draft", "sent"].includes(record.status)).length, note: `${inventory.length} stock items watched`, icon: "fa-clipboard" },
            { label: "For Canvass", value: records.filter((record) => record.sedar_canvassing_required && !record.sedar_canvassing_done).length, note: "over budget checks", icon: "fa-send" },
            { label: "For Approval", value: records.filter((record) => record.status === "to_approve").length, note: "needs sign-off", icon: "fa-check-square-o" },
            { label: "Late / Risk", value: records.filter((record) => record.delivery_performance === "risk" || record.approval_age_days > 5).length, note: "budget or supplier watch", icon: "fa-exclamation-triangle" },
        ];
    }

    buildFlow(records) {
        const columns = [
            { key: "draft", label: "RFQ", items: [] },
            { key: "sent", label: "RFQ Sent", items: [] },
            { key: "to_approve", label: "Approval", items: [] },
            { key: "purchase", label: "PO", items: [] },
            { key: "done", label: "Locked", items: [] },
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
            const code = item.default_code ? `[${item.default_code}] ` : "";
            actions.push({ label: item.sedar_critical_part ? "Critical part" : "Inventory watch", title: `${code}${item.name}`, detail: `${item.qty_available || 0} on hand${item.sedar_item_size ? ` - ${item.sedar_item_size}` : ""}` });
        }
        for (const record of records.filter((item) => item.status === "to_approve" || item.delivery_performance !== "good").slice(0, 4)) {
            actions.push({ label: record.statusLabel, title: record.title, detail: record.sedar_canvassing_required ? "Canvas needed" : record.requested_by || record.supplier || "Assign owner" });
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
        return `PHP ${new Intl.NumberFormat("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value || 0)}`;
    }

    formatShortDate(value) {
        return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
    }

    openRecords() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_records_board");
    }

    async getFlowFormViewId() {
        if (!this.flowFormViewId) {
            this.flowFormViewId = await this.orm.call("purchase.order", "action_sedar_get_flow_form_view_id", []);
        }
        return this.flowFormViewId;
    }

    async openRecord(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        const viewId = await this.getFlowFormViewId();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "purchase.order",
            res_id: recordId,
            views: [[viewId, "form"]],
            target: "current",
        });
    }

    openNewPurchaseRequest() {
        this.action.doAction("sedar_procurement.action_sedar_purchase_rfq");
    }

    openCanvasSheet() {
        this.action.doAction("sedar_procurement.action_sedar_purchase_canvas");
    }

    openCreatePo() {
        this.action.doAction("sedar_procurement.action_sedar_purchase_po");
    }
}

registry.category("actions").add("sedar_procurement_dashboard", SedarProcurementDashboard);

export class SedarProcurementRecordsBoard extends Component {
    static template = "sedar_procurement.ProcurementRecordsBoard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.flowFormViewId = null;
        this.state = useState({ records: [], activeType: "all" });

        onWillStart(async () => {
            await this.loadRecords();
        });
    }

    async loadRecords() {
        const records = await this.orm.searchRead(
            "purchase.order",
            [],
            ["id", "name", "partner_id", "user_id", "date_order", "date_planned", "amount_total", "state", "sedar_budget_amount", "sedar_over_budget", "sedar_canvassing_required", "sedar_canvassing_done", "sedar_urgent_exception", "sedar_quote_count"],
            { order: "date_order desc, id desc", limit: 80 }
        );
        this.state.records = records.map((record) => this.normalizeRecord(record));
    }

    normalizeRecord(record) {
        const performance = this.getPerformance(record);
        const partner = Array.isArray(record.partner_id) ? record.partner_id[1] : "Supplier not set";
        const requester = Array.isArray(record.user_id) ? record.user_id[1] : "Owner not set";
        return {
            ...record,
            ref: record.name || `PO-${record.id}`,
            title: partner,
            supplier: partner,
            requested_by: requester,
            status: record.state,
            record_type: record.state === "purchase" || record.state === "done" ? "po" : "rfq",
            statusLabel: STATUS_LABELS[record.state] || "RFQ",
            typeLabel: record.state === "purchase" || record.state === "done" ? "Purchase Order" : "RFQ",
            performanceLabel: performance.label,
            performanceClass: performance.className,
            amountLabel: this.formatCurrency(record.amount_total),
            dateLabel: this.formatDate(record.date_order),
            deliveryLabel: this.formatDate(record.date_planned),
        };
    }

    getPerformance(record) {
        if (record.sedar_over_budget || record.sedar_canvassing_required) {
            return PERFORMANCE_META.risk;
        }
        if (record.state === "to_approve" || record.sedar_urgent_exception) {
            return PERFORMANCE_META.watch;
        }
        return PERFORMANCE_META.good;
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

    async getFlowFormViewId() {
        if (!this.flowFormViewId) {
            this.flowFormViewId = await this.orm.call("purchase.order", "action_sedar_get_flow_form_view_id", []);
        }
        return this.flowFormViewId;
    }

    async openRecord(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        const viewId = await this.getFlowFormViewId();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "purchase.order",
            res_id: recordId,
            views: [[viewId, "form"]],
            target: "current",
        });
    }

    openNewPurchaseRequest() {
        this.action.doAction("sedar_procurement.action_sedar_purchase_rfq");
    }

    openCanvasSheet() {
        this.action.doAction("sedar_procurement.action_sedar_purchase_canvas");
    }

    openCreatePo() {
        this.action.doAction("sedar_procurement.action_sedar_purchase_po");
    }

    formatCurrency(value) {
        return `PHP ${new Intl.NumberFormat("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value || 0)}`;
    }

    formatDate(value) {
        if (!value) {
            return "No date";
        }
        return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
    }
}

registry.category("actions").add("sedar_procurement_records_board", SedarProcurementRecordsBoard);

const INVENTORY_STATUS_META = {
    ok: { label: "OK", className: "is-good" },
    low: { label: "Low Stock", className: "is-watch" },
    critical: { label: "Critical", className: "is-risk" },
};

const INVENTORY_CATEGORY_LABELS = {
    spare: "Spare Parts",
    fuel: "Fuel",
    lubricant: "Lubricants",
    office: "Office Supplies",
};

const PRODUCT_STATUS_META = {
    ok: { key: "ok", label: "OK", className: "is-good" },
    low: { key: "low", label: "Low Stock", className: "is-watch" },
    critical: { key: "critical", label: "Critical", className: "is-risk" },
};

export class SedarStockReorderSignalsBoard extends Component {
    static template = "sedar_procurement.StockReorderSignalsBoard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ items: [], activeStatus: "watch" });

        onWillStart(async () => {
            await this.loadItems();
        });
    }

    async loadItems() {
        const items = await this.orm.searchRead(
            "product.product",
            [["purchase_ok", "=", true]],
            ["id", "name", "default_code", "categ_id", "qty_available", "virtual_available", "sedar_item_size", "sedar_critical_part", "sedar_vessel_id"],
            { order: "name", limit: 100 }
        );
        this.state.items = items.map((item) => this.normalizeItem(item));
    }

    normalizeItem(item) {
        const quantity = item.qty_available || 0;
        const forecast = item.virtual_available || 0;
        const status = this.getProductStatus(item, quantity, forecast);
        const vessel = Array.isArray(item.sedar_vessel_id) ? item.sedar_vessel_id[1] : "";
        const category = Array.isArray(item.categ_id) ? item.categ_id[1] : "Inventory";
        const code = item.default_code ? `[${item.default_code}] ` : "";
        return {
            ...item,
            status: status.key,
            statusLabel: status.label,
            statusClass: status.className,
            categoryLabel: INVENTORY_CATEGORY_LABELS[category] || category || "Inventory",
            name: `${code}${item.name}`,
            quantity_on_hand: quantity,
            reorder_point: item.sedar_critical_part ? 2 : 5,
            quantityLabel: this.formatNumber(quantity),
            reorderLabel: this.formatNumber(item.sedar_critical_part ? 2 : 5),
            locationLabel: vessel ? `Assigned to ${vessel}` : "General tug inventory",
            procurement_signal: forecast < quantity ? "Forecast demand is reducing stock" : "",
            maintenance_demand: item.sedar_critical_part ? "Critical tugboat part" : item.sedar_item_size || "",
        };
    }

    getProductStatus(item, quantity, forecast) {
        if (item.sedar_critical_part && quantity <= 1) {
            return PRODUCT_STATUS_META.critical;
        }
        if (quantity <= 0 || forecast < 0) {
            return PRODUCT_STATUS_META.critical;
        }
        if (quantity <= 5 || forecast <= 2) {
            return PRODUCT_STATUS_META.low;
        }
        return PRODUCT_STATUS_META.ok;
    }

    get watchItems() {
        return this.state.items.filter((item) => item.status !== "ok" || item.quantity_on_hand <= item.reorder_point);
    }

    get filteredItems() {
        if (this.state.activeStatus === "all") {
            return this.state.items;
        }
        if (this.state.activeStatus === "critical") {
            return this.state.items.filter((item) => item.status === "critical");
        }
        return this.watchItems;
    }

    get summary() {
        return {
            total: this.state.items.length,
            watch: this.watchItems.length,
            critical: this.state.items.filter((item) => item.status === "critical").length,
        };
    }

    get stockKpis() {
        const low = this.state.items.filter((item) => item.status === "low").length;
        const critical = this.state.items.filter((item) => item.status === "critical").length;
        const linked = this.watchItems.filter((item) => item.procurement_signal || item.maintenance_demand).length;
        return [
            { label: "Watch List", value: this.summary.watch, note: "at or below reorder point", icon: "fa-archive" },
            { label: "Critical", value: critical, note: "needs fast action", icon: "fa-exclamation-triangle" },
            { label: "Low Stock", value: low, note: "plan replenishment", icon: "fa-level-down" },
            { label: "Linked Demand", value: linked, note: "maintenance or PR signal", icon: "fa-link" },
        ];
    }

    setStatus(ev) {
        this.state.activeStatus = ev.currentTarget.dataset.status;
    }

    openDashboard() {
        this.action.doAction("sedar_procurement.action_sedar_procurement_dashboard");
    }

    openInventoryList() {
        this.action.doAction("stock.product_template_action_product");
    }

    openItem(ev) {
        const recordId = Number(ev.currentTarget.dataset.id);
        if (!recordId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatNumber(value) {
        return new Intl.NumberFormat("en-PH", { maximumFractionDigits: 2 }).format(value || 0);
    }
}

registry.category("actions").add("sedar_stock_reorder_signals_board", SedarStockReorderSignalsBoard);

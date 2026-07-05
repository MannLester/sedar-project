/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_META = {
    valid: { label: "Valid", color: "#28a745" },
    renewal: { label: "For Renewal", color: "#ffca2c" },
    expired: { label: "Expired", color: "#dc3545" },
    missing: { label: "No Expiry", color: "#3f3f43" },
};

const TYPE_LABELS = {
    contract: "Contracts",
    vessel_certificate: "Vessel Certificates",
    insurance: "Insurance",
    permit: "Permits",
    board_resolution: "Board Resolutions",
    iso: "ISO Documents",
};

export class SedarDocumentRiskDashboard extends Component {
    static template = "sedar_marine_mvp.DocumentRiskDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            total: 0,
            statuses: [],
            categories: [],
            donutStyle: "",
            criticalCount: 0,
            renewalCount: 0,
            expiredCount: 0,
            missingCount: 0,
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const records = await this.orm.searchRead(
            "sedar.document.control",
            [],
            ["document_type", "status", "expiry_date"]
        );
        const statusCounts = { valid: 0, renewal: 0, expired: 0, missing: 0 };
        const categoryCounts = {};

        for (const type of Object.keys(TYPE_LABELS)) {
            categoryCounts[type] = { valid: 0, renewal: 0, expired: 0, total: 0 };
        }

        for (const record of records) {
            const status = record.expiry_date ? record.status || "missing" : "missing";
            const type = record.document_type;
            statusCounts[status] = (statusCounts[status] || 0) + 1;

            if (categoryCounts[type]) {
                const barStatus = status === "missing" ? "expired" : status;
                categoryCounts[type][barStatus] += 1;
                categoryCounts[type].total += 1;
            }
        }

        const total = records.length || 0;
        const statuses = Object.entries(STATUS_META).map(([key, meta]) => {
            const count = statusCounts[key] || 0;
            return {
                key,
                label: meta.label,
                color: meta.color,
                count,
                percent: total ? Math.round((count / total) * 100) : 0,
            };
        });

        this.state.total = total;
        this.state.statuses = statuses;
        this.state.categories = Object.entries(categoryCounts)
            .map(([key, counts]) => ({
                key,
                label: TYPE_LABELS[key],
                valid: counts.valid,
                renewal: counts.renewal,
                expired: counts.expired,
                total: counts.total,
                validPct: counts.total ? (counts.valid / counts.total) * 100 : 0,
                renewalPct: counts.total ? (counts.renewal / counts.total) * 100 : 0,
                expiredPct: counts.total ? (counts.expired / counts.total) * 100 : 0,
            }))
            .filter((category) => category.total > 0);
        this.state.criticalCount = statusCounts.renewal + statusCounts.expired + statusCounts.missing;
        this.state.renewalCount = statusCounts.renewal;
        this.state.expiredCount = statusCounts.expired;
        this.state.missingCount = statusCounts.missing;
        this.state.donutStyle = this.buildDonutStyle(statuses);
        this.state.loading = false;
    }

    buildDonutStyle(statuses) {
        if (!this.state.total) {
            return "background: #e5e9ef;";
        }
        let cursor = 0;
        const stops = [];
        for (const status of statuses) {
            if (!status.count) {
                continue;
            }
            const end = cursor + (status.count / this.state.total) * 360;
            stops.push(`${status.color} ${cursor}deg ${end}deg`);
            cursor = end;
        }
        return `background: conic-gradient(${stops.join(", ")});`;
    }

    getLegendValue(status) {
        return `${status.count} (${status.percent}%)`;
    }

    openStatus(statusKey) {
        const domain = statusKey === "missing" ? [["expiry_date", "=", false]] : [["status", "=", statusKey]];
        this.openRegister(domain);
    }

    openCategory(categoryKey) {
        this.openRegister([["document_type", "=", categoryKey]]);
    }

    openRiskRegister() {
        this.openRegister(["|", "|", ["status", "=", "renewal"], ["status", "=", "expired"], ["expiry_date", "=", false]]);
    }

    openRegister(domain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Document Control Register",
            res_model: "sedar.document.control",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
        });
    }
}

registry.category("actions").add("sedar_document_risk_dashboard", SedarDocumentRiskDashboard);

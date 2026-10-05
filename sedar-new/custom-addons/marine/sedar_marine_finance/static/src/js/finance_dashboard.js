/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";


export class SedarFinanceDashboard extends Component {
    static template = "sedar_marine_finance.FinanceDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, error: false, data: false });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.data = await this.orm.call(
                "sedar.finance.dashboard", "get_dashboard_data", []
            );
        } catch (error) {
            this.state.error = true;
            this.notification.add("Unable to load Finance Operations.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get summaryCards() {
        const summary = this.state.data.summary;
        return [
            { label: "Net customer invoices", value: summary.net_invoiced, help: "Posted invoices less posted credit notes", tone: "navy" },
            { label: "Open receivables", value: summary.outstanding, help: "Amount still due from customers", tone: "blue", action: "open" },
            { label: "Overdue receivables", value: summary.overdue, help: "Past due and not fully settled", tone: "red", action: "overdue" },
            { label: "Payments / credits applied", value: summary.applied, help: "Posted invoice value no longer outstanding", tone: "green" },
        ];
    }

    get pipelineCards() {
        const pipeline = this.state.data.pipeline;
        return [
            { key: "billing_review", label: "Ready for billing review", value: pipeline.billing_review, help: "Completed services awaiting Finance review", icon: "fa-clipboard" },
            { key: "pricing_exception", label: "Pricing exceptions", value: pipeline.pricing_exception, help: "Services blocked by a pricing issue", icon: "fa-exclamation-triangle", warning: true },
            { key: "draft_invoice", label: "Draft invoices", value: pipeline.draft_invoice, help: "Prepared but not posted to the ledger", icon: "fa-file-text-o" },
        ];
    }

    get receivableCards() {
        const receivables = this.state.data.receivables;
        return [
            { key: "open", label: "Open", value: receivables.open },
            { key: "partial", label: "Partially paid", value: receivables.partial },
            { key: "overdue", label: "Overdue", value: receivables.overdue, warning: true },
            { key: "paid", label: "Paid", value: receivables.paid },
            { key: "credit_notes", label: "Credit notes", value: receivables.credit_notes },
        ];
    }

    formatMoney(value, currency = false) {
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: currency || this.state.data.currency,
            maximumFractionDigits: 0,
        }).format(value || 0);
    }

    async openAction(key) {
        const target = this.state.data.actions[key];
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: target.name,
            res_model: target.res_model,
            views: [[false, "list"], [false, "form"]],
            domain: target.domain,
            context: { create: false },
        });
    }

    async openRecord(item) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: item.title,
            res_model: item.model,
            res_id: item.res_id,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("sedar_finance_dashboard", SedarFinanceDashboard);

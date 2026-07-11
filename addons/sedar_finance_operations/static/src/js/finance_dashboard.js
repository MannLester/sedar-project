/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const ACTIONS = {
    petty: "sedar_finance_operations.action_petty_cash",
    advance: "sedar_finance_operations.action_cash_advance",
    disbursement: "sedar_finance_operations.action_disbursement",
    collection: "sedar_finance_operations.action_collection",
    billing: "sedar_tug_ops.action_sedar_towage_billing",
};

export class FinanceDashboard extends Component {
    static template = "sedar_finance_operations.FinanceDashboard";
    static props = ["action", "actionId", "className"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.openAction = this.openAction.bind(this);
        this.openNew = this.openNew.bind(this);
        this.openRecord = this.openRecord.bind(this);
        this.openRecordByKey = this.openRecordByKey.bind(this);
        this.ACTIONS = ACTIONS;
        this.state = useState({
            loading: true,
            error: "",
            currency: { id: false, name: "", symbol: "", position: "before", decimal_places: 2 },
            metrics: { available: 0, pending: 0, advances: 0, checks: 0, ar: 0, ap: 0 },
            approvals: [],
            banks: [],
            advances: [],
            activity: [],
        });
        this.quickEntries = [
            { label: "Petty expense", note: "Record a cash outlay", icon: "fa-ticket", action: ACTIONS.petty, model: "sedar.finance.petty.cash" },
            { label: "Cash advance", note: "Fund an employee", icon: "fa-user", action: ACTIONS.advance, model: "sedar.finance.cash.advance" },
            { label: "Disbursement", note: "Prepare cash or check", icon: "fa-pencil-square-o", action: ACTIONS.disbursement, model: "sedar.finance.disbursement" },
            { label: "Collection", note: "Log customer receipt", icon: "fa-download", action: ACTIONS.collection, model: "sedar.finance.collection" },
            { label: "Towage billing", note: "Prepare service billing", icon: "fa-ship", action: ACTIONS.billing, model: "sedar.towage.billing" },
        ];
        this.reports = [
            { label: "General Ledger", action: "account_financial_report.action_general_ledger_wizard" },
            { label: "Trial Balance", action: "account_financial_report.action_trial_balance_wizard" },
            { label: "P&L", action: "sedar_finance_operations.action_profit_loss_comparison" },
            { label: "Balance Sheet", action: "sedar_finance_operations.action_balance_sheet_comparison" },
            { label: "Cash Flow", action: "sedar_finance_operations.action_cash_flow_report" },
        ];
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const snapshot = await this.orm.call("sedar.finance.dashboard", "get_snapshot", []);
            const companies = snapshot.companies || [];
            const petty = snapshot.petty || [];
            const advances = snapshot.advances || [];
            const disbursements = snapshot.disbursements || [];
            const collections = snapshot.collections || [];
            const invoices = snapshot.invoices || [];
            const bills = snapshot.bills || [];
            const banks = snapshot.banks || [];
            const billings = snapshot.billings || [];
            const pettyCount = snapshot.petty_count || 0;
            const advanceCount = snapshot.advance_count || 0;
            const disbursementCount = snapshot.disbursement_count || 0;

            const currencyId = this.idOf(companies[0]?.currency_id);
            const currencies = snapshot.currencies || [];
            this.currencies = Object.fromEntries(currencies.map((currency) => [currency.id, currency]));
            this.state.currency = this.currencies[currencyId] || this.state.currency;
            const bookBanks = banks.filter((row) => !this.idOf(row.currency_id) || this.idOf(row.currency_id) === currencyId);
            const releasedAdvances = advances.filter((row) => ["released", "partial"].includes(row.state));
            const releasedChecks = disbursements.filter((row) => row.state === "released" && ["outstanding", "stale"].includes(row.check_status));
            this.state.metrics = {
                available: this.sum(bookBanks, "sedar_available_cash"),
                pending: pettyCount + advanceCount + disbursementCount,
                advances: this.sum(releasedAdvances, "outstanding_amount"),
                checks: this.sum(releasedChecks.filter((row) => !this.idOf(row.currency_id) || this.idOf(row.currency_id) === currencyId), "amount"),
                ar: this.sum(invoices, "amount_residual_signed"),
                ap: Math.abs(this.sum(bills, "amount_residual_signed")),
            };
            this.state.approvals = [
                ...petty.map((row) => this.approvalRow(row, "Petty cash", "sedar.finance.petty.cash", "description")),
                ...advances.filter((row) => row.state === "submitted").map((row) => this.approvalRow(row, "Advance", "sedar.finance.cash.advance", "purpose", "employee_id")),
                ...disbursements.filter((row) => row.state === "submitted").map((row) => this.approvalRow(row, "Disbursement", "sedar.finance.disbursement", "supplier_id")),
            ].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 10);
            this.state.banks = banks;
            this.state.advances = releasedAdvances.slice(0, 8);
            this.state.activity = [
                ...collections.map((row) => this.activityRow(row, "Collection", "in", row.deposit_date, "customer_id", "sedar.finance.collection")),
                ...billings.map((row) => this.activityRow(row, "Towage billing", "bill", row.write_date, "customer_id", "sedar.towage.billing")),
                ...disbursements.filter((row) => row.state === "released").map((row) => this.activityRow(row, "Disbursement", "out", row.date, "supplier_id", "sedar.finance.disbursement")),
            ].sort((a, b) => b.sortDate.localeCompare(a.sortDate)).slice(0, 12);
        } catch (error) {
            console.error("Finance dashboard failed to load", error);
            this.state.error = error.message || "The finance data could not be loaded.";
        } finally {
            this.state.loading = false;
        }
    }

    idOf(value) {
        return Array.isArray(value) ? value[0] : (value || false);
    }

    labelOf(value, fallback = "Not set") {
        return Array.isArray(value) && value[1] ? value[1] : fallback;
    }

    sum(rows, field) {
        return rows.reduce((total, row) => total + (Number(row[field]) || 0), 0);
    }

    approvalRow(row, type, model, detailField, partnerField) {
        const detail = partnerField ? this.labelOf(row[partnerField], row[detailField] || "No detail") : (row[detailField] || "No detail");
        return { id: row.id, model, type, reference: row.name || "Draft", detail, amount: row.amount, date: row.date || "", currencyId: this.idOf(row.currency_id) };
    }

    activityRow(row, type, tone, date, partnerField, model) {
        return {
            id: row.id, model, type, tone, reference: row.name || "Draft",
            partner: this.labelOf(row[partnerField]), amount: row.amount,
            date: this.shortDate(date), sortDate: date || "", currencyId: this.idOf(row.currency_id),
        };
    }

    formatMoney(value, currencyId) {
        const currency = this.currencies?.[currencyId] || this.state.currency;
        const amount = Number(value) || 0;
        try {
            return new Intl.NumberFormat(undefined, {
                style: currency.name ? "currency" : "decimal",
                currency: currency.name || undefined,
                currencyDisplay: "narrowSymbol",
                minimumFractionDigits: currency.decimal_places ?? 2,
                maximumFractionDigits: currency.decimal_places ?? 2,
            }).format(amount);
        } catch {
            const figure = amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return `${currency.symbol || currency.name || ""} ${figure}`.trim();
        }
    }

    formatBook(value) {
        return this.formatMoney(value, this.state.currency.id);
    }

    currencyCode(currencyId) {
        return (this.currencies?.[currencyId] || this.state.currency).name || "Book currency";
    }

    shortDate(value) {
        if (!value) return "No date";
        return String(value).slice(0, 10);
    }

    ageInDays(value) {
        if (!value) return 0;
        return Math.max(0, Math.floor((Date.now() - new Date(`${value}T00:00:00`).getTime()) / 86400000));
    }

    openAction(action) {
        return this.action.doAction(action);
    }

    openNew(model) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            views: [[false, "form"]],
            target: "current",
            context: {},
        });
    }

    openRecord(model, id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: model, res_id: id, views: [[false, "form"]], target: "current" });
    }

    openRecordByKey(event, model, id) {
        if (["Enter", " "].includes(event.key)) {
            event.preventDefault();
            this.openRecord(model, id);
        }
    }
}

registry.category("actions").add("sedar_finance_operations.finance_dashboard", FinanceDashboard);

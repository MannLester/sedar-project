/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const VESSELS = [
    {
        name: "M/TUG SEDAR 1",
        role: "Harbor assist tug",
        lat: 18,
        lng: 14,
        status: "Active",
        statusClass: "is-good",
        location: "Batangas Anchorage",
        tracking: "Online",
        speed: "7.8 kn",
        heading: "142 deg",
        eta: "14:40",
        engine: "Caterpillar 3516B",
        horsepower: "4,200 HP",
        bollard: "52 t",
        fuel: 68,
        availability: 94,
        parts: [
            { name: "Main engine oil filter", stock: "18 pcs", state: "OK", className: "is-good" },
            { name: "Steering pump seal kit", stock: "2 pcs", state: "Low", className: "is-watch" },
            { name: "Fire pump impeller", stock: "6 pcs", state: "OK", className: "is-good" },
        ],
    },
    {
        name: "M/TUG SEDAR 2",
        role: "Terminal standby tug",
        lat: 32,
        lng: 43,
        status: "Active",
        statusClass: "is-good",
        location: "Manila Bay Terminal",
        tracking: "Stale",
        speed: "0.0 kn",
        heading: "Docked",
        eta: "On berth",
        engine: "Niigata 6L28HX",
        horsepower: "3,600 HP",
        bollard: "45 t",
        fuel: 51,
        availability: 88,
        parts: [
            { name: "Radar scanner belt", stock: "0 pcs", state: "Reorder", className: "is-risk" },
            { name: "Generator AVR", stock: "4 pcs", state: "OK", className: "is-good" },
            { name: "Air compressor kit", stock: "1 set", state: "Watch", className: "is-watch" },
        ],
    },
    {
        name: "M/TUG SEDAR 3",
        role: "Towage support tug",
        lat: 15,
        lng: 78,
        status: "On Maintenance",
        statusClass: "is-watch",
        location: "Navotas Yard",
        tracking: "Offline",
        speed: "N/A",
        heading: "N/A",
        eta: "Jul 18",
        engine: "Yanmar 6EY26W",
        horsepower: "3,200 HP",
        bollard: "38 t",
        fuel: 22,
        availability: 61,
        parts: [
            { name: "Port propeller repair", stock: "In yard", state: "In yard", className: "is-risk" },
            { name: "Shaft bearing", stock: "Ordered", state: "Ordered", className: "is-watch" },
            { name: "Hull coating", stock: "In progress", state: "In progress", className: "is-watch" },
        ],
    },
];

for (let number = 4; number <= 9; number++) {
    const source = VESSELS[(number - 1) % 3];
    const mapPositions = [
        [18, 14], [32, 43], [15, 78],
        [58, 18], [45, 57], [64, 84],
        [72, 10], [68, 48], [74, 76],
    ];
    VESSELS.push({
        ...source,
        name: `M/TUG SEDAR ${number}`,
        lat: mapPositions[number - 1][0],
        lng: mapPositions[number - 1][1],
        parts: [],
    });
}

const WORKFLOWS = [
    { label: "Payroll Preview", value: "PHP 1.42M", note: "crew payroll estimate, deductions pending", icon: "fa-id-badge", className: "is-watch" },
    { label: "Dry Dock Control", value: "1 Tug", note: "Lakan: 63% yard progress", icon: "fa-wrench", className: "is-risk" },
    { label: "Audit / ISO", value: "7 Open", note: "3 evidence packets due this week", icon: "fa-check-square-o", className: "is-watch" },
    { label: "Bank Feed Preview", value: "PHP 8.7M", note: "book cash after uncleared checks", icon: "fa-university", className: "is-good" },
];

const TIMELINE = [
    { time: "08:10", title: "AIS ping received", detail: "Aurora reported 7.8 kn near Batangas Anchorage.", className: "is-good" },
    { time: "09:25", title: "Inventory barcode scan", detail: "Steering pump seal kit issued to MT SEDAR Marikit.", className: "is-watch" },
    { time: "10:00", title: "Payroll batch drafted", detail: "23 crew records included; statutory deductions are in preview mode.", className: "is-watch" },
    { time: "11:30", title: "Dry dock milestone updated", detail: "Lakan hull coating moved to in-progress.", className: "is-risk" },
    { time: "13:15", title: "ISO evidence request", detail: "Safety meeting record requested from HSSE owner.", className: "is-watch" },
];

const KPI_TRENDS = [
    { label: "Fleet Availability", value: 86, target: 90, points: [72, 78, 81, 84, 82, 86], note: "8 of 9 vessels ready", icon: "fa-anchor", gradientId: "FleetAvailability" },
    { label: "Utilization", value: 71, target: 80, points: [58, 61, 67, 63, 69, 71], note: "Job hours / available hours", icon: "fa-briefcase", gradientId: "Utilization" },
    { label: "Gross Margin", value: 34, target: 40, points: [24, 28, 29, 31, 33, 34], note: "Towage after fuel, crew, vendor bills", icon: "fa-line-chart", gradientId: "GrossMargin" },
    { label: "Compliance", value: 92, target: 95, points: [84, 86, 89, 91, 90, 92], note: "Certificates, medicals, ISO, permits", icon: "fa-check-circle", gradientId: "Compliance" },
];

const FINANCIAL_DATA = {
    months: ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"],
    revenue: [4200, 4500, 4800, 5100, 4900, 5300, 5600, 5400, 5800, 6100, 6400, 6662],
    opex: [3100, 3200, 3400, 3500, 3300, 3600, 3800, 3700, 3900, 4100, 4200, 4300],
    currency: "PHP",
    unit: "K",
};

const FLEET_UTILIZATION = [
    { name: "SEDAR 1", working: 68, idle: 12, standby: 14, drydock: 6 },
    { name: "SEDAR 2", working: 54, idle: 8, standby: 38, drydock: 0 },
    { name: "SEDAR 3", working: 0, idle: 0, standby: 0, drydock: 100 },
    { name: "SEDAR 4", working: 72, idle: 10, standby: 13, drydock: 5 },
    { name: "SEDAR 5", working: 61, idle: 15, standby: 19, drydock: 5 },
    { name: "SEDAR 6", working: 45, idle: 20, standby: 30, drydock: 5 },
];

const REVENUE_BY_SERVICE = [
    { label: "Harbor Assist", value: 3800, color: "#0f6b72" },
    { label: "Coastal Towing", value: 1400, color: "#0f3b4a" },
    { label: "Ferry Services", value: 850, color: "#c87913" },
    { label: "Salvage Ops", value: 612, color: "#b83b31" },
];

const MODULES = [
    { title: "AIS / GPS Control", text: "Map-style vessel location, speed, heading, stale signal warning, and dispatch context.", status: "Visualization ready" },
    { title: "Owner Vessel Card", text: "Engine, horsepower, bollard pull, fuel, availability, and critical parts per tug.", status: "Visualization ready" },
    { title: "Payroll", text: "Crew payroll batch, overtime, deductions, contributions, and journal posting preview.", status: "General flow" },
    { title: "Dry Dock", text: "Yard timeline, contractor status, scope, cost exposure, and dispatch blocking.", status: "General flow" },
    { title: "Audit / ISO", text: "Audit plan, evidence checklist, document revision, retention, and sign-off.", status: "General flow" },
    { title: "Inventory Barcode", text: "Scan part, identify vessel/bin, issue to maintenance or tug operation.", status: "General flow" },
    { title: "Bank Feed", text: "Imported transactions, matching status, book balance, and outstanding checks.", status: "Preview only" },
    { title: "KPI Trends", text: "Targets and trends for availability, utilization, margin, and compliance.", status: "Visualization ready" },
];

const ACTION_FOCUS = {
    "sedar_owner_preview.dashboard": "Owner Preview",
    "sedar_owner_preview.fleet_map": "AIS / GPS Control",
    "sedar_owner_preview.vessel_health": "Owner Vessel Card",
    "sedar_owner_preview.payroll": "Payroll",
    "sedar_owner_preview.dry_dock": "Dry Dock",
    "sedar_owner_preview.audit_iso": "Audit / ISO",
    "sedar_owner_preview.inventory_barcode": "Inventory Barcode",
    "sedar_owner_preview.bank_feed": "Bank Feed",
    "sedar_owner_preview.kpi_trends": "KPI Trends",
};

const ACTION_VESSEL = {
    "sedar_owner_preview.dry_dock": 2,
    "sedar_owner_preview.vessel_health": 1,
};

const FOCUS_COPY = {
    "Owner Preview": {
        kicker: "",
        title: "Executive Dashboard",
        intro: "A board-ready overview of your tug operations.",
    },
    "AIS / GPS Control": {
        kicker: "Marine Operations",
        title: "AIS / GPS Map Preview",
        intro: "A map-style command screen for tug locations, GPS signal age, speed, heading, job assignment, and dispatch risk. This is the expected final direction once real GPS trackers are connected.",
    },
    "Owner Vessel Card": {
        kicker: "Marine Operations",
        title: "Vessel Health Preview",
        intro: "A tug-owner view of each boat: engine, horsepower, bollard pull, fuel, availability, running status, and critical spare parts.",
    },
    Payroll: {
        kicker: "Human Resources",
        title: "Payroll Preview",
        intro: "A general payroll flow for tug crew: vessel assignment, hours, overtime, allowances, deductions, statutory contributions, approval, and posting preview.",
    },
    "Dry Dock": {
        kicker: "Technical / Maintenance",
        title: "Dry Dock Preview",
        intro: "A dry dock control page showing yard progress, scope, contractor accountability, cost exposure, and the reason a tug is blocked from dispatch.",
    },
    "Audit / ISO": {
        kicker: "HSSE / Document Control",
        title: "Audit / ISO Preview",
        intro: "A compliance workflow for audit plans, evidence packets, ISO revision control, document retention, and management sign-off.",
    },
    "Inventory Barcode": {
        kicker: "Procurement / Inventory",
        title: "Inventory Barcode Preview",
        intro: "A scanner-style flow for issuing parts to a tug, connecting stock movement to maintenance, vessel, and job context.",
    },
    "Bank Feed": {
        kicker: "Finance and Accounting",
        title: "Bank Feed Preview",
        intro: "A finance preview for imported bank transactions, matching status, book balance, statement balance, and outstanding checks.",
    },
    "KPI Trends": {
        kicker: "Executive Dashboard",
        title: "KPI Trends Preview",
        intro: "A board-level trend view for availability, utilization, profitability, compliance, and operating exceptions.",
    },
};

const PAYROLL_ROWS = [
    { crew: "Capt. Jun Mercado", vessel: "MT SEDAR Aurora", hours: "176", overtime: "18", gross: "PHP 78,400", deductions: "PHP 9,820", net: "PHP 68,580", state: "For HR review" },
    { crew: "Engr. Paolo Reyes", vessel: "MT SEDAR Marikit", hours: "168", overtime: "12", gross: "PHP 64,700", deductions: "PHP 8,140", net: "PHP 56,560", state: "Ready" },
    { crew: "Bosun Mark Flores", vessel: "MT SEDAR Lakan", hours: "154", overtime: "6", gross: "PHP 42,600", deductions: "PHP 5,380", net: "PHP 37,220", state: "Dry dock costed" },
];

const DRY_DOCK_MILESTONES = [
    { name: "Hull inspection", owner: "Navotas Yard", progress: 100, state: "Done" },
    { name: "Port propeller repair", owner: "Propulsion contractor", progress: 72, state: "In progress" },
    { name: "Shaft bearing replacement", owner: "Procurement + Yard", progress: 45, state: "Waiting part" },
    { name: "Sea trial and clearance", owner: "Technical Manager", progress: 0, state: "Next" },
];

const AUDIT_ROWS = [
    { item: "ISO 9001 vessel maintenance procedure", owner: "Document Control", due: "Jul 15", state: "For review" },
    { item: "Safety meeting attendance evidence", owner: "HSSE", due: "Jul 13", state: "Missing evidence" },
    { item: "Permit renewal sign-off", owner: "Operations", due: "Jul 18", state: "Ready" },
    { item: "Internal audit corrective action", owner: "Technical", due: "Jul 20", state: "Open" },
];

const BARCODE_STEPS = [
    { label: "Scan", value: "SP-STEER-SEAL-002", note: "Steering pump seal kit" },
    { label: "Identify", value: "Bin B-04 / Main Store", note: "2 pcs available before issue" },
    { label: "Assign", value: "MT SEDAR Marikit", note: "Linked to maintenance request MR-0241" },
    { label: "Post", value: "1 pc issued", note: "Creates stock move and vessel cost" },
];

const BANK_ROWS = [
    { date: "Jul 10", bank: "BDO Operating", detail: "Harbor Gateway Terminal payment", amount: "PHP 1,250,000", match: "Matched to invoice" },
    { date: "Jul 10", bank: "BPI Payroll", detail: "Crew payroll funding", amount: "PHP -1,420,000", match: "For approval" },
    { date: "Jul 09", bank: "BDO Operating", detail: "Check 004218 cleared", amount: "PHP -318,500", match: "Matched to PO disbursement" },
    { date: "Jul 09", bank: "Metrobank", detail: "Unknown deposit", amount: "PHP 85,000", match: "Needs review" },
];

export class OwnerPreviewDashboard extends Component {
    static template = "sedar_owner_preview.OwnerPreviewDashboard";
    static props = ["action", "actionId", "className"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        const tag = this.props.action?.tag || "sedar_owner_preview.dashboard";
        this.selectVessel = this.selectVessel.bind(this);
        this.closeMapDetails = this.closeMapDetails.bind(this);
        this.selectModule = this.selectModule.bind(this);
        this.sparkline = this.sparkline.bind(this);
        this.sparklineArea = this.sparklineArea.bind(this);
        this.kpiStatus = this.kpiStatus.bind(this);
        this.kpiTrend = this.kpiTrend.bind(this);
        this.kpiColor = this.kpiColor.bind(this);
        this.financialArea = this.financialArea.bind(this);
        this.financialLine = this.financialLine.bind(this);
        this.utilBarSegments = this.utilBarSegments.bind(this);
        this.doughnutPath = this.doughnutPath.bind(this);
        this.openAction = this.openAction.bind(this);
        this.state = useState({
            activeVessel: ACTION_VESSEL[tag] || 0,
            activeModule: ACTION_FOCUS[tag] || "Owner Preview",
            loading: true,
            generatedAt: "",
            alerts: [],
            mapZoomed: (ACTION_FOCUS[tag] || "Owner Preview") === "Owner Vessel Card",
        });
        this.vessels = VESSELS;
        this.workflows = WORKFLOWS;
        this.timeline = TIMELINE;
        this.trends = KPI_TRENDS;
        this.financialData = FINANCIAL_DATA;
        this.fleetUtil = FLEET_UTILIZATION;
        this.revenueByService = REVENUE_BY_SERVICE;
        this.modules = MODULES;
        this.payrollRows = PAYROLL_ROWS;
        this.dryDockMilestones = DRY_DOCK_MILESTONES;
        this.auditRows = AUDIT_ROWS;
        this.barcodeSteps = BARCODE_STEPS;
        this.bankRows = BANK_ROWS;
        onWillStart(() => this.loadOwnerSnapshot());
    }

    async loadOwnerSnapshot() {
        try {
            const snapshot = await this.orm.call("sedar.dashboard", "get_owner_snapshot", []);
            this.state.generatedAt = snapshot.generated_at;
            this.state.alerts = snapshot.alerts;
            if (snapshot.metrics?.length) {
                this.workflows = snapshot.metrics;
            }
            if (snapshot.vessels?.length) {
                this.vessels = snapshot.vessels;
                this.state.activeVessel = Math.min(this.state.activeVessel, snapshot.vessels.length - 1);
            }
        } finally {
            this.state.loading = false;
        }
    }

    get focusCopy() {
        return FOCUS_COPY[this.state.activeModule] || FOCUS_COPY["Owner Preview"];
    }

    get isOverview() {
        return this.state.activeModule === "Owner Preview";
    }

    get selectedVessel() {
        return this.vessels[this.state.activeVessel] || this.vessels[0];
    }

    get mapZoomStyle() {
        if (!this.state.mapZoomed) {
            return "";
        }
        const vessel = this.selectedVessel;
        return `transform-origin: ${vessel.lng}% ${vessel.lat}%; transform: scale(1.3);`;
    }

    selectVessel(index) {
        this.state.activeVessel = index;
        this.state.mapZoomed = true;
    }

    closeMapDetails() {
        this.state.mapZoomed = false;
    }

    selectModule(module) {
        this.state.activeModule = module.title;
    }

    sparkline(points) {
        const max = Math.max(...points);
        const min = Math.min(...points);
        const span = max - min || 1;
        return points.map((value, index) => {
            const x = (index / (points.length - 1 || 1)) * 100;
            const y = 100 - ((value - min) / span) * 68 - 10;
            return `${x},${y}`;
        }).join(" ");
    }

    sparklineArea(points) {
        const max = Math.max(...points);
        const min = Math.min(...points);
        const span = max - min || 1;
        const coords = points.map((value, index) => {
            const x = (index / (points.length - 1 || 1)) * 100;
            const y = 100 - ((value - min) / span) * 68 - 10;
            return `${x},${y}`;
        });
        return `0,80 ${coords.join(" ")} 100,80`;
    }

    kpiStatus(value, target) {
        const ratio = value / target;
        if (ratio >= 0.95) return "good";
        if (ratio >= 0.8) return "watch";
        return "risk";
    }

    kpiTrend(points) {
        const last = points[points.length - 1];
        const prev = points[points.length - 2];
        if (last > prev) return "up";
        if (last < prev) return "down";
        return "flat";
    }

    kpiColor(value, target) {
        const ratio = value / target;
        if (ratio >= 0.95) return "#0f3b4a";
        if (ratio >= 0.8) return "#c87913";
        return "#b83b31";
    }

    financialArea(series, maxY) {
        const w = 600;
        const h = 200;
        const pad = 10;
        const coords = series.map((v, i) => {
            const x = pad + (i / (series.length - 1)) * (w - pad * 2);
            const y = h - pad - (v / maxY) * (h - pad * 2);
            return `${x},${y}`;
        });
        return `${pad},${h - pad} ${coords.join(" ")} ${w - pad},${h - pad}`;
    }

    financialLine(series, maxY) {
        const w = 600;
        const h = 200;
        const pad = 10;
        return series.map((v, i) => {
            const x = pad + (i / (series.length - 1)) * (w - pad * 2);
            const y = h - pad - (v / maxY) * (h - pad * 2);
            return `${x},${y}`;
        }).join(" ");
    }

    utilBarSegments(vessel) {
        const total = vessel.working + vessel.idle + vessel.standby + vessel.drydock;
        if (total === 0) return [];
        const segments = [];
        let offset = 0;
        const colors = { working: "#0f3b4a", idle: "#b83b31", standby: "#c87913", drydock: "#687f85" };
        for (const key of ["working", "idle", "standby", "drydock"]) {
            const pct = (vessel[key] / total) * 100;
            if (pct > 0) {
                segments.push({ key, pct, offset, color: colors[key] });
                offset += pct;
            }
        }
        return segments;
    }

    doughnutPath(index, total) {
        const cx = 90;
        const cy = 90;
        const r = 70;
        const inner = 48;
        const gap = 1.5 * (Math.PI / 180);
        let cumulative = 0;
        for (let i = 0; i < index; i++) {
            cumulative += REVENUE_BY_SERVICE[i].value;
        }
        const grandTotal = REVENUE_BY_SERVICE.reduce((s, d) => s + d.value, 0);
        const startAngle = (cumulative / grandTotal) * 2 * Math.PI - Math.PI / 2 + gap;
        cumulative += REVENUE_BY_SERVICE[index].value;
        const endAngle = (cumulative / grandTotal) * 2 * Math.PI - Math.PI / 2 - gap;
        const largeArc = (endAngle - startAngle) > Math.PI ? 1 : 0;
        const x1 = cx + r * Math.cos(startAngle);
        const y1 = cy + r * Math.sin(startAngle);
        const x2 = cx + r * Math.cos(endAngle);
        const y2 = cy + r * Math.sin(endAngle);
        const ix1 = cx + inner * Math.cos(startAngle);
        const iy1 = cy + inner * Math.sin(startAngle);
        const ix2 = cx + inner * Math.cos(endAngle);
        const iy2 = cy + inner * Math.sin(endAngle);
        return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${inner} ${inner} 0 ${largeArc} 0 ${ix1} ${iy1} Z`;
    }

    openAction(action) {
        if (action) {
            this.action.doAction(action);
        }
    }
}

registry.category("actions").add("sedar_owner_preview.dashboard", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.fleet_map", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.vessel_health", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.payroll", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.dry_dock", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.audit_iso", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.inventory_barcode", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.bank_feed", OwnerPreviewDashboard);
registry.category("actions").add("sedar_owner_preview.kpi_trends", OwnerPreviewDashboard);

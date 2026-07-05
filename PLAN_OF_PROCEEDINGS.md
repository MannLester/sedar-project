# Plan Of Proceedings

## Principle

Everything in `resources/Web System.pdf` must be represented in the MVP dashboard. For MVP, "represented" means the module appears as a dashboard section, metric, alert, table, or drill-down using sample data. It does not mean every module is a full production ERP workflow yet.

The MVP should prove:

- We understand the full business system requested in the PDF.
- We can connect departments into one operating view.
- We can show executive decisions from operational data.
- The only missing pieces are actual SEDAR data and confirmed SEDAR-specific processes.

## Recommended Starting Order

### Step 1: Build The Dashboard Map First

Start with the dashboard, not the forms.

Reason:

The PDF is executive in nature. It asks for a system that gives management visibility across the company. If the dashboard is defined first, every workflow and data table can be built to feed a clear business decision.

Output:

- Final dashboard sections.
- KPI list.
- Module coverage checklist.
- Drill-down requirements.

Use [DASHBOARD_COVERAGE_MATRIX.md](DASHBOARD_COVERAGE_MATRIX.md) as the source checklist.

### Step 2: Define The Sample Data Model

Create the minimum data needed to make every dashboard section believable.

Required sample entities:

- Vessels.
- Customers.
- Jobs.
- Voyage logs.
- Fuel logs.
- Crew members.
- Crew certificates.
- Maintenance work orders.
- Spare parts.
- Inventory items.
- Purchase requests.
- Purchase orders.
- Suppliers.
- Invoices.
- Payments.
- Health, safety, and environment incidents.
- Risk assessments.
- Training records.
- Employee records.
- Contracts.
- Vessel certificates.
- Insurance records.
- Permits.
- Board resolutions.
- ISO documents.

Output:

- Data dictionary.
- Seed data file or mock API.
- Relationship map.

### Step 3: Build The President Dashboard

This is the first screen of the MVP.

It should include:

- Financial snapshot.
- Fleet utilization.
- Vessel availability.
- Job performance.
- Maintenance risk.
- Health, safety, and environment risk.
- Crew compliance.
- Procurement and inventory risk.
- Document expiry risk.
- Profitability by vessel/customer/job type.

Output:

- Working president overview page.
- Drill-down links to module pages or tables.

### Step 4: Build Module Dashboards

After the president dashboard, build the department pages:

- Finance and Accounting.
- Tug Operations.
- Technical and Maintenance.
- Health, Safety, and Environment.
- Crewing.
- Procurement.
- Inventory.
- Human Resources.
- Document Control.
- Management Dashboard.

Each module page should have:

- KPI cards.
- A status table.
- Alerts.
- Recent activity.
- Drill-down detail view.

Output:

- One usable page per module.
- Consistent status model.

### Step 5: Build The End-To-End Demo Workflow (also mentioned in MVP Interpretation section in PDF_ANALYSIS.md)

Create one connected demo path:

1. Customer requests tug service.
2. Operations creates a job order.
3. Dispatcher assigns tug and crew.
4. Voyage log records hours, fuel, delay, and completion.
5. Billing data updates finance.
6. Vessel utilization and profitability update president dashboard.
7. Maintenance, health, safety, and environment, crew, procurement, inventory, and document alerts remain visible.

Output:

- Demo script.
- Demo records.
- One complete job-to-cash walkthrough.

### Step 6: Add Drill-Down Detail Screens

Only add detail screens needed to explain dashboard numbers.

Priority detail screens:

- Vessel profile.
- Job order detail.
- Crew profile.
- Maintenance work order detail.
- Invoice detail.
- Inventory item detail.
- Purchase order detail.
- Health, safety, and environment incident detail.
- Document detail.

Output:

- Clickable path from dashboard KPI to source records.

### Step 7: Prepare Presentation Mode

Before presentation, make sure the MVP clearly says:

- Data is sample data.
- Processes are generic tugboat business processes.
- SEDAR-specific rules will be configured after discovery.

Output:

- Demo script.
- Discovery questions.
- Gap list between MVP and production.
- Implementation roadmap after deal closing.

## Build Priority

### Priority 1: Must Be In First Demo

- President dashboard.
- Tug operations dashboard.
- Vessel availability/utilization.
- Job order and voyage log sample data.
- Finance summary with billing, AR, cash flow, and profitability.
- Maintenance work orders and downtime.
- Crew certification alerts.
- Health, safety, and environment incidents and corrective actions.
- Inventory reorder alerts.
- Procurement approvals.
- Document expiry alerts.

### Priority 2: Should Be In First Demo If Time Allows

- Human Resource attendance summary.
- Payroll summary placeholder.
- Budget versus actual.
- Fixed assets register.
- Dry docking plan.
- Barcode support placeholder.
- Training records.
- Supplier performance.

### Priority 3: Clearly Mark As Future Production Integration

- Live GPS/AIS tracking.
- Bank integration.
- Full payroll computation.
- Full accounting posting.
- Digital signature integration.
- Microsoft 365/SharePoint integration.
- Power BI embedded deployment.
- Odoo or maritime ERP implementation.

## Dashboard Rule

No PDF module should be hidden only in documentation. Every module should be visible on screen through at least one of these:

- KPI card.
- Alert.
- Status table.
- Trend chart.
- Summary widget.
- Drill-down page.
- Expiry list.
- Activity list.

## First Week Proceedings

### Day 1: Scope And Dashboard Checklist

- Review PDF requirements.
- Approve dashboard modules.
- Approve sample-data assumptions.
- Confirm demo story.

### Day 2: Data Model And Seed Data

- Define entities.
- Create sample records.
- Confirm KPI formulas.

### Day 3: President Dashboard

- Build overview layout.
- Add cards, charts, and alerts.
- Connect sample data.

### Day 4: Operations, Fleet, Finance

- Build job, dispatch, vessel, and finance dashboard sections.
- Connect job-to-cash sample records.

### Day 5: Maintenance, Crew, Health, Safety, And Environment, Procurement, Inventory, Documents

- Build risk and compliance sections.
- Add expiry and overdue alerts.
- Add module tables.

### Day 6: Drill-Downs And Demo Flow

- Add detail views.
- Validate drill-down paths.
- Run full demo story.

### Day 7: Polish And Presentation

- Clean labels and layout.
- Confirm every PDF item is represented.
- Prepare demo script and post-deal discovery list.

## Definition Of Ready

We are ready to build when:

- Dashboard coverage matrix is accepted.
- Sample data list is accepted.
- First demo story is accepted.
- Technology stack is chosen.

## Definition Of Done

The MVP is done when:

- Every PDF module appears in the dashboard.
- Every major KPI uses sample data.
- The president dashboard tells the business story in one screen.
- The demo can run from job request to billing impact.
- The team can clearly explain what is generic, what is sample, and what requires SEDAR confirmation.

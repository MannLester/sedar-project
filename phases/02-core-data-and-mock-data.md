# Phase 2: Core Data And Mock Data

## Goal

Create the sample data model and seeded records needed to make the MVP feel operationally real.

## Master Data

Create sample records for:

- Vessels.
- Customers.
- Crew members.
- Service types.
- Ports and locations.
- Suppliers.
- Inventory items.
- Maintenance equipment.
- HSE categories.
- Document types.

## Transaction Data

Create sample records for:

- Job orders.
- Dispatch assignments.
- Voyage logs.
- Fuel logs.
- Invoices and collections.
- Maintenance work orders.
- Purchase requests and purchase orders.
- Inventory movements.
- HSE incidents and corrective actions.
- Document expiry records.

## Suggested Sample Counts

- 5 to 8 vessels.
- 25 to 40 crew members.
- 8 to 12 customers.
- 80 to 150 job orders.
- 20 to 40 invoices.
- 20 to 30 maintenance work orders.
- 50 to 100 inventory items.
- 10 to 20 purchase records.
- 8 to 15 HSE records.
- 30 to 50 controlled documents.

## Essential Relationships

The MVP data must connect:

- Job order to customer, vessel, crew, fuel log, invoice, and voyage log.
- Vessel to maintenance, certificates, fuel, utilization, downtime, and profitability.
- Crew member to vessel assignment, certificates, medical status, and training.
- Inventory item to work order, purchase order, supplier, and reorder level.
- HSE issue to vessel, job, corrective action, owner, and closure date.
- Invoice to customer, job, payment status, and aging bucket.

## Data Quality Rules

- Sample data must look plausible and internally consistent.
- No real personal data should be used.
- All demo records should be clearly synthetic.
- Dates should include past, current, and upcoming records so alerts and trends are visible.
- Each dashboard KPI must trace back to visible records.

## Deliverables

- Data dictionary.
- Entity relationship diagram or concise schema map.
- Sample seed data.
- KPI calculation notes.
- Known assumptions list.

## Acceptance Criteria

- A user can inspect a dashboard number and find the sample records behind it.
- Vessel availability, utilization, revenue, maintenance, HSE, crew, and document expiry data all update from the same dataset.
- Demo records cover normal, delayed, overdue, high-cost, and high-risk scenarios.


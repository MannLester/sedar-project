# Phase 3: Core Workflows

## Goal

Build the connected workflows that prove the MVP is more than a dashboard mockup.

## Workflow 1: Job-To-Cash

Steps:

1. Create customer service request.
2. Convert request to job order.
3. Assign tug and crew.
4. Dispatch job.
5. Record actual start, finish, hours, fuel, delay, and remarks.
6. Mark job complete.
7. Generate billing summary.
8. Update invoice status and receivables.

Key screens:

- Customer request form.
- Job order list and detail page.
- Dispatch board or schedule calendar.
- Voyage log form.
- Billing summary.

MVP proof:

- A completed job changes vessel utilization, revenue, fuel usage, and customer receivables.

## Workflow 2: Maintenance-To-Availability

Steps:

1. Create planned maintenance or defect work order.
2. Set severity and due date.
3. Reserve parts or create purchase request.
4. Mark vessel status as under maintenance if needed.
5. Complete work order.
6. Return vessel to available status.

Key screens:

- Vessel profile.
- Maintenance work order list.
- Work order detail page.
- Spare parts usage panel.

MVP proof:

- Maintenance downtime affects vessel availability and the executive dashboard.

## Workflow 3: Crew Readiness

Steps:

1. Maintain crew profile and role.
2. Track certifications, medicals, training, and availability.
3. Warn dispatcher if crew assignment has expired or expiring documents.
4. Show upcoming certification risks.

Key screens:

- Crew list.
- Crew profile.
- Certification expiry alerts.
- Assignment panel inside dispatch.

MVP proof:

- Crew readiness affects dispatch confidence and compliance alerts.

## Workflow 4: Procure-To-Stock

Steps:

1. Create purchase request.
2. Approve request.
3. Convert to purchase order.
4. Receive items into inventory.
5. Update stock level and reorder alerts.

Key screens:

- Inventory list.
- Purchase request form.
- Purchase order list.
- Receiving form.

MVP proof:

- Inventory shortage creates risk for maintenance completion and operations readiness.

## Workflow 5: HSE Action Tracking

Steps:

1. Record incident, near miss, inspection finding, or audit issue.
2. Assign corrective action.
3. Track due date and closure status.
4. Show unresolved HSE actions on dashboard.

Key screens:

- HSE incident form.
- Corrective action list.
- Vessel or job linked HSE history.

MVP proof:

- HSE records produce open action counts and trend indicators.

## Deliverables

- Working workflow screens.
- Status model for each workflow.
- Role-based action notes.
- Demo script covering all workflows.

## Acceptance Criteria

- Every workflow can be completed from start to finish using sample data.
- Status changes are visible immediately.
- Workflow results update at least one management KPI.
- The system clearly separates demo assumptions from confirmed future rules.


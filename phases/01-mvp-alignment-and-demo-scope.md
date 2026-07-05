# Phase 1: MVP Alignment And Demo Scope

## Goal

Define a focused MVP that demonstrates SEDAR's future integrated tug ERP and fleet management system without needing real company data or final business rules.

## Key Message

The MVP proves capability. Real data, exact approval rules, and company-specific processes will be plugged in after the deal is closed.

## Scope Decisions

Build the demo around these connected areas:

- Executive dashboard.
- Tug operations.
- Vessel and fleet records.
- Crewing readiness.
- Maintenance and work orders.
- Inventory and procurement signals.
- Finance summary for billing, receivables, and profitability.
- HSE incident and action tracking.
- Document expiry alerts.

Defer these until discovery:

- Real accounting configuration.
- Payroll computation.
- Bank integration.
- Live AIS/GPS integration.
- Exact SEDAR approval hierarchy.
- Final report formats.
- Mobile offline workflows.
- Government or third-party integrations.

## MVP Demo Story

Use this story as the spine of the demo:

1. A customer requests a ship assist or towage job.
2. Operations creates a job order.
3. Dispatcher assigns a tug and checks crew availability.
4. The job is completed with actual hours, delay reason, fuel usage, and voyage notes.
5. The job creates a billable transaction and updates revenue.
6. Maintenance and HSE records affect vessel availability.
7. The president sees the impact in the executive dashboard.

## Deliverables

- Approved MVP scope.
- Demo workflow map.
- Demo roles and permissions list.
- List of assumptions and placeholders.
- Definition of sample data required for the demo.

## Acceptance Criteria

- The demo can be explained in less than 10 minutes.
- Every screen supports the core story.
- Every company-specific assumption is visibly marked as sample or placeholder.
- The MVP has a clear path to real data replacement.

## Suggested Build Notes

- Keep navigation department-based but dashboard-led.
- Use realistic tugboat terms, not generic logistics-only terms.
- Make status changes visible across modules.
- Avoid building isolated screens that do not affect any dashboard or workflow.


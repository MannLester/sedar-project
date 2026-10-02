# MVP Data Requirements From A Tugboat Company President's View

As president, I would want the system to answer one question every day:

"Are our vessels, people, cash, and customers producing profitable, safe, reliable service?"

## Executive Snapshot

The first dashboard should show:

- Total revenue this month.
- Gross margin by tug, customer, and job type.
- Vessel utilization percentage.
- Vessel availability percentage.
- Jobs completed, jobs delayed, and jobs cancelled.
- Open receivables and aging.
- Fuel cost and fuel variance.
- Maintenance downtime.
- Safety incidents and near misses.
- Crew certification expiry risks.
- Cash position and next 30-day cash obligations.

## Vessel And Fleet Data

Important fields:

- Vessel name, registry number, type, horsepower, bollard pull, class, home port, operating status.
- Availability status: available, assigned, under maintenance, dry dock, off-hire.
- Last job date, next scheduled job, current location.
- Fuel capacity, fuel on hand, fuel consumption per hour, fuel variance.
- Planned maintenance due dates.
- Critical equipment status.
- Vessel certificate and insurance expiry dates.

Business decisions supported:

- Which tug is making money?
- Which tug is idle too often?
- Which tug causes the most delays or maintenance cost?
- Which vessel should be prioritized for repair, replacement, or redeployment?

## Customer And Revenue Data

Important fields:

- Customer name, customer type, billing terms, contract status.
- Service type: harbor assist, barge tow, escort, standby, emergency response, special project.
- Job order, quote, dispatch record, voyage log, invoice, payment status.
- Revenue, direct cost, gross margin, discount, tax, receivable age.

Business decisions supported:

- Which customers are profitable?
- Which customers consume capacity but pay slowly?
- Which job types produce the best margins?
- Which contracts need rate adjustment?

## Operations Data

Important fields:

- Job number, customer, requested service, pickup location, destination, required time, assigned tug, assigned crew.
- Job status: requested, quoted, approved, scheduled, dispatched, in progress, completed, billed, paid.
- Actual start time, actual end time, waiting time, delay reason.
- Fuel used, distance or hours worked, standby time, overtime.
- Customer feedback or service issue flag.

Business decisions supported:

- Are dispatchers assigning the right vessel?
- Which delays are controllable?
- Are we billing all chargeable waiting time and standby time?
- Are jobs being closed and billed quickly?

## Crew And HR Data

Important fields:

- Crew profile, rank, certifications, STCW documents, medical certificate, training records.
- Availability, shift, vessel assignment, leave status.
- Overtime hours, fatigue risk, payroll link.
- Certification expiry alerts.

Business decisions supported:

- Do we have enough qualified crew for upcoming jobs?
- Which certifications will expire soon?
- Are we overusing certain crew members?
- Can we accept a new job without creating compliance or fatigue risk?

## Maintenance Data

Important fields:

- Planned maintenance schedule by vessel and equipment.
- Work orders, defect reports, severity, root cause, assigned technician, target completion.
- Spare parts used, maintenance cost, downtime hours.
- Dry dock plan and budget.
- Repeat defects by equipment.

Business decisions supported:

- Which maintenance issues threaten operations?
- Which vessels have rising cost trends?
- Are we doing preventive maintenance before failure?
- What budget is needed for dry dock and critical spares?

## Inventory And Procurement Data

Important fields:

- Spare parts, fuel, lubricants, consumables, warehouse location, quantity on hand, reorder point.
- Purchase request, purchase order, supplier, approval status, delivery status.
- Last purchase price, lead time, supplier reliability.

Business decisions supported:

- Which critical parts are below reorder level?
- Which suppliers delay operations?
- Are purchase approvals causing job or maintenance delays?
- Are fuel and lubricant costs moving against budget?

## HSE And Compliance Data

Important fields:

- Incidents, near misses, unsafe acts, inspections, audits, risk assessments.
- Permit status, corrective actions, responsible person, target closure date.
- Safety meeting attendance and training records.

Business decisions supported:

- Are safety issues increasing?
- Which vessels or job types carry higher risk?
- Are corrective actions being closed on time?
- Are we ready for audits and customer compliance checks?

## Document Control Data

Important fields:

- Contracts, vessel certificates, insurance, permits, board resolutions, ISO documents.
- Owner department, expiry date, renewal owner, renewal status.
- Document version and approval status.

Business decisions supported:

- Which documents can stop operations if not renewed?
- Are contracts and permits visible to the right departments?
- Do we have a defensible audit trail?

## Recommended MVP Dataset

Use sample data with enough variety to make dashboards meaningful:

- 5 to 8 vessels.
- 25 to 40 crew members.
- 8 to 12 customers.
- 80 to 150 job orders across 3 months.
- 20 to 40 invoices with mixed payment statuses.
- 20 to 30 maintenance work orders.
- 50 to 100 inventory items.
- 10 to 20 purchase requests and purchase orders.
- 8 to 15 HSE records.
- 30 to 50 controlled documents with expiry dates.


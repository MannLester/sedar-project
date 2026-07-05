# Public Research Notes

## SEDAR-Specific Result

I did not find reliable public business-process documentation for "SEDAR Tug Services, Inc." or "SEDAR Tug" during the initial search pass. Because of that, we should not claim any company-specific process as confirmed.

For the MVP, the safe position is:

- Use generic tugboat and marine service workflows.
- Mark all data as sample/demo data.
- Treat SEDAR-specific approval rules, forms, billing rates, vessel records, crew records, and compliance reports as discovery items after deal closing.

## Public Tug Business Patterns We Can Safely Align With

Publicly visible tug and marine companies commonly describe services around:

- Harbor or port towage.
- Terminal towage.
- Ship assist.
- Escort services.
- Barge or coastal towage.
- Offshore support.
- Salvage or emergency response.
- Pilotage or port-related marine support in some groups.

These support the MVP's generic service types:

- Ship assist.
- Barge tow.
- Escort.
- Standby.
- Emergency or special operation.
- Terminal support.

## Sources Checked

- Svitzer is described publicly as providing harbor and terminal towage services across many ports and terminals: https://en.wikipedia.org/wiki/Maersk
- PSA Marine is described publicly as providing pilotage and port or terminal towage: https://en.wikipedia.org/wiki/PSA_International
- Boluda Towage is described publicly as operating harbor, coastal, and offshore towage, plus salvage and support services: https://es.wikipedia.org/wiki/Boluda_Corporaci%C3%B3n_Mar%C3%ADtima
- General tugboat operations include ship assist, barge towing, escort, harbor support, and requirements based on vessel size and port rules: https://en.wikipedia.org/wiki/Tugboat

These are not SEDAR-specific operating procedures. They are only used to validate generic service categories for the demo.

## Practical Business Processes To Borrow For MVP

### Job-To-Cash

1. Customer requests a tug service.
2. Operations records job details and required schedule.
3. Commercial or finance confirms quote/rate.
4. Dispatcher assigns vessel and crew.
5. Tug completes service and logs actual hours, delays, fuel, and events.
6. Job is reviewed and approved for billing.
7. Invoice is issued.
8. Collection status updates the customer and executive dashboard.

### Maintenance-To-Availability

1. Vessel reports defect or reaches planned maintenance due date.
2. Maintenance creates a work order.
3. Required spare parts are reserved or requested.
4. Work order is completed and downtime is recorded.
5. Vessel returns to available status.
6. Cost, downtime, and repeat defect data update dashboard KPIs.

### Procure-To-Stock

1. Department raises purchase request.
2. Approval is routed based on amount and item type.
3. Purchase order is issued to supplier.
4. Goods are received into inventory.
5. Stock level updates.
6. Invoice is matched and prepared for payment.

### Crew Readiness

1. Crew records and certificates are maintained.
2. Scheduler checks availability and certification status before assignment.
3. Expiring documents trigger alerts.
4. Crew assignments flow into operations logs and payroll summaries.

### HSE Action Tracking

1. Incident, near miss, audit finding, or inspection issue is recorded.
2. Corrective action is assigned.
3. Responsible person updates progress.
4. Closure is reviewed.
5. Open risk and incident trends update the dashboard.


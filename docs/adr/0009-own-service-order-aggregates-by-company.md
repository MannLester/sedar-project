# Own Service Order aggregates by company

Every Service Order belongs to exactly one required company. The company defaults from the
active company when the Service Order is created and cannot change afterward. Operational,
dispatch, inventory, finance, and procurement records that are children of a Service Order
inherit that ownership. Company-aware links and record rules prevent records from different
companies from being combined or exposed together.

## Status

Accepted

## Context

Service Orders previously had no company owner even though Odoo users, invoices, inventory
locations, Purchase Requests, and accounting transactions are company-aware. A user allowed in
multiple companies could therefore connect operational facts across company boundaries, and a
single-company user could receive records whose ownership was ambiguous.

## Decision

- `sedar.marine.service.order.company_id` is required, indexed, defaults to the active company,
  is not copied, and is immutable after creation.
- Operational descendants store the company related from their Service Order and use global
  allowed-company record rules. Company checks apply to every relationship where both sides own
  a company. Explicit constraints cover nested relationships that Odoo cannot infer by itself.
- Crew-shortage actions inherit the aggregate company. A shortage escalated to Manpower Planning
  creates and links only a Manpower Request in that same company.
- Portal and executive-dashboard reads that intentionally use elevated access must still include
  an explicit enabled-company or dashboard-company predicate.
- Existing Service Orders are migrated from company-owned client/contact, invoice, Purchase
  Request, and inventory-location evidence. Exactly one candidate is accepted. Conflicting
  candidates abort the upgrade with the affected record IDs; no evidence falls back to Odoo's
  main company.
- Company-neutral HSSE records, Marketing records, tariff configuration, crew master data, and
  marine location master data remain outside this aggregate boundary.
- Tugboat company ownership is intentionally deferred to Issue #6, where the fleet-asset and
  stock-location ownership contract can be introduced together.

## Consequences

- Company ownership cannot be repaired by moving a live Service Order; incorrect ownership must
  be corrected before creating related transactions or through a controlled data migration.
- Multi-company users see a Company field in operational views. Single-company users continue
  to use the active company without extra UI noise.
- Modules extending the aggregate must expose the inherited company, enforce compatible links,
  and add company-scoped access in the same change.

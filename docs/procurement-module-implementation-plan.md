# SEDAR Procurement Module Implementation Plan

## Goal

Build the Procurement workspace around the company's actual flow: Maintenance or Inventory confirms a physical-goods need, the Procurement and Inventory Officer compares partial supplier Bids per product, awards each product line to one Bidder, and creates one standard Odoo Purchase Order per winning supplier. The same work will expose Equipment Running Hours and procurement context from the simulated AIS map and separate warehouse Storage from goods Currently In Use on tugboats.

## Status

Implemented for the Odoo 19 demonstration. Delivery and final release verification are tracked by
GitHub issue #1 and its ordered child issues #2–#9. This document remains the accepted scope and
verification contract; it is not a list of unfinished work.

## Confirmed scope

- “Items” on the fleet map are Equipment, not Inventory Items.
- Running Hours are cumulative hour-meter readings, not trip time or Actual Service Time.
- Running Hour Readings are dated and attributable; the latest valid reading is current.
- A Running Hours threshold notifies Maintenance for review. It never starts procurement automatically.
- Maintenance submits a Purchase Request only after confirming a need.
- Submission assigns an actionable Odoo activity to the Procurement and Inventory Officer.
- Purchase Requests cover physical Inventory Items, tugboat spare parts, and Replacement Equipment only. Labor and external maintenance services are excluded.
- Suppliers send quotations through existing channels. The Officer records each Bid and attaches the received quotation; there is no supplier portal.
- A Bidder may quote any subset of Purchase Request lines.
- Each product line's full quantity is awarded to one Bidder. Quantities are not split at award time.
- Multiple Bidders may win different lines in one Purchase Request.
- Awarded lines are grouped by winning supplier into separate standard Odoo Purchase Orders.
- Awards are manual best-value decisions with a required reason, not automatic lowest-price selection.
- Procurement and Inventory Officer is the only procurement business role in this scope. “Purchase Request Manager” must not appear in business-facing copy.
- The map shows active procurement first and a separate procurement history for selected Equipment.
- Inventory Issue no longer means immediate consumption. Goods move from Storage to a tugboat and
  remain Currently In Use until a controlled return, consumption, or disposal. Technical Removal
  does not close the lifecycle or move stock.

## Delivered implementation

The active `sedar-new/` implementation provides Running Hour Readings, vendorless physical-goods
Purchase Requests, partial Bid capture, immutable Line Awards, supplier-grouped standard Purchase
Orders, stock-backed Storage and Currently In Use, and Equipment procurement drill-down from the
Simulated AIS Feed. The Procurement navigation contains Purchase Requests, Bidder List, Purchase
Orders, Storage, and Currently In Use. Standard Odoo continues to own Purchase Orders, receipts,
supplier bills, stock movements, and accounting records.

## Ownership boundaries

- SEDAR Maintenance owns Equipment, Running Hour Readings, maintenance thresholds, and technical review.
- SEDAR Procurement owns Purchase Requests, received Bids, comparisons, Line Awards, award reasons, and the handoff to ordering.
- Standard Odoo Purchase owns Purchase Orders and their normal confirmation lifecycle.
- Standard Odoo Inventory owns receipts, locations, stock quantities, transfers, removals, returns, and consumption movements.
- Standard Odoo Accounting owns supplier bills, payments, and ledger entries.
- The simulated AIS module presents read-only projections from these owning records; it does not become their source of truth.

## Delivered domain model

### Running Hour Readings

Add `sedar.equipment.running.hour.reading` with:

- Equipment
- cumulative Running Hours
- reading date and time
- recorded by
- optional note and evidence attachment
- validity/correction audit metadata

Extend `maintenance.equipment` with the reading relationship and computed current Running Hours, next service due hours, hours remaining, and due/overdue state. Valid readings must be non-negative and must not silently reduce the cumulative meter. Corrections preserve the original record rather than deleting history.

When the latest reading reaches the last verified service reading plus the planned interval, create one non-duplicating Maintenance activity for technical review. Maintenance remains responsible for deciding whether parts or Replacement Equipment are needed.

### Purchase Requests

Extend `sedar.purchase.request` to:

- link the affected Equipment when the need is equipment-specific;
- remove the preferred-vendor requirement from approval;
- hold multiple Bids and multiple resulting Purchase Orders;
- expose bidding, partial-award, fully-awarded, and ordered progress;
- assign the submitted-request review activity to the configured Procurement and Inventory Officer;
- prevent Purchase Order creation while any required line lacks a valid Line Award.

Existing request source links to maintenance work orders, inventory shortages, and Service Orders remain.

### Bids and Line Awards

Add one Bid header per Bidder and Purchase Request, plus Bid lines for the subset quoted by that supplier.

The Bid header records:

- Purchase Request and Bidder
- received date
- validity date
- promised delivery date
- payment terms
- warranty or commercial notes
- attached supplier quotation
- status and audit metadata

Each Bid line records the quoted Purchase Request line, full requested quantity, unit price, subtotal, availability, and line-specific delivery or notes. Absence of a Bid line means that Bidder did not quote that product.

Each Purchase Request line points to its current immutable Line Award. The award snapshots the winning Bid line, supplier, price, quantity/UoM, award reason, awarded by/at, commercial-exception facts, reset audit, and generated Purchase Order line. Award rules:

- only quoted lines may be awarded;
- one request line has at most one winner;
- the winning Bid must cover the line's full quantity;
- an award reason is mandatory;
- changing an approved award requires an audited reset before a Purchase Order exists;
- an awarded line cannot silently change after its Purchase Order is created.
- a zero-price quote requires explicit confirmation;
- an expired Bid requires an explicit company-local-date override and reason;
- an unquoted line blocks ordering until the Officer irreversibly cancels it with reason/actor/time.

For the MVP, all Bids use the Purchase Request currency. Foreign-currency normalization and exchange-rate snapshots are deferred.

### Purchase Order handoff

After all required lines are awarded, group Line Awards by Bidder and create one standard `purchase.order` per winning supplier. Each order contains only that supplier's awarded lines and preserves the Purchase Request and Bid references in origin/source links.

The operation is idempotent and concurrency-safe: request/line locks plus database uniqueness prevent duplicate Purchase Orders and source lines. Generated orders cannot be deleted; cancellation remains linked history and standard Reset to Draft remains available. Standard Odoo then handles order confirmation, receipts, supplier bills, and accounting.

### Storage and Currently In Use

Change a new Inventory Issue to create a standard internal stock movement from warehouse Storage to the tugboat's stock location. Preserve the immutable issue event and add a lifecycle record that identifies:

- Item Type and quantity
- tugboat
- related Equipment when installed or assigned to a specific machine
- issue and installation dates
- current state: issued, currently in use, removed, or consumed
- source and closing stock movements
- responsible users and notes

Storage is calculated from warehouse locations. Currently In Use is calculated from open tugboat lifecycle records and reconciled with standard stock movements. Removal must move reusable goods to a selected internal Storage location; consumption or disposal must move goods to the appropriate controlled non-internal destination. Direct quant updates remain fixture-only under ADR-0004.

Replacement Equipment received through a Purchase Order remains a product until Maintenance records installation, at which point it creates or links the individually tracked Equipment identity.

Historical one-step issues are preserved as completed legacy consumption. The upgrade must not rewrite their done stock moves or pretend they are currently aboard.

## Workflow

1. An Engineer or Maintenance user records a Running Hour Reading.
2. A due threshold creates one Maintenance review activity; it does not create purchasing records.
3. Maintenance identifies required physical goods and submits a Purchase Request linked to the work order and Equipment.
4. Submission assigns an Odoo activity to the Procurement and Inventory Officer.
5. The Officer reviews and approves the internal request.
6. Supplier quotations arrive through existing channels; the Officer records one Bid per participating supplier and its quoted product lines.
7. The comparison view shows all Bidders under each requested product.
8. The Officer selects one winner for each product line and enters a mandatory best-value justification.
9. The system groups won lines by supplier and creates one standard Purchase Order per winner.
10. Standard Odoo receipts replenish Storage.
11. A controlled Inventory Issue moves goods from Storage to the named tugboat.
12. Installed or assigned goods remain under Currently In Use until an explicit return, consumption,
    or disposal records the next controlled stock movement. Technical Removal preserves that balance.

## User interface

Use this Procurement navigation:

- Purchase Requests
- Bidder List
- Purchase Orders
- Inventory
  - Storage
  - Currently In Use

### Purchase Request

- Header status for internal review, bidding, award, and ordering progress.
- Product lines with Officer-only award/cancel actions, current award, and award status; mobile keeps the row actions beside the product so they do not require horizontal scrolling.
- A dedicated Bid comparison action grouped by requested product, plus a per-line award picker showing Bidder, price, delivery, validity, availability, and warranty before confirmation.
- Smart buttons for Bids and generated Purchase Orders.
- Chatter and activities for request and award audit history.

### Bidder List

- Default grouping by Purchase Request and product.
- Show Bidder, quoted price, delivery, availability, validity, warranty/terms, award state, and attached quotation.
- Filters for active bidding, incomplete award, awarded, not awarded, and historical.
- A comparison action opens all Bids for one Purchase Request side by side.

### Inventory

- Storage shows warehouse quantities, reservations, Available to Issue, reorder status, and location.
- Currently In Use shows tugboat, Item Type, quantity, related Equipment, issue/install date, and lifecycle state.
- Controlled actions handle issue, install/assign, remove, and consume; users never edit quantities directly.

### Fleet map

When a tugboat marker is selected, retain status, crew, and location, then add an Equipment section showing:

- Equipment name, system, criticality, and maintenance status
- current Running Hours
- next service due and remaining/overdue hours
- active procurement count

Selecting Equipment opens:

- Active Procurement: related open Purchase Requests, products, Bidders, commercial summary, and Line Award state.
- Procurement History: previous winning Bidders and resulting Purchase Orders.

Equipment and Running Hours are visible to authorized Fleet Monitoring and Maintenance users. Bid prices, attachments, and commercial terms are returned only when the viewer also has Procurement and Inventory Officer access. The shared demo override may make all sections visible during demonstration, but it is not the production permission model.

## Roles and security

### Maintenance users

- Record Running Hour Readings and evidence.
- Receive due-review activities.
- Create and submit equipment-linked Purchase Requests.
- Cannot record Bids, award lines, or create Purchase Orders.

### Procurement and Inventory Officer

- Reviews and approves submitted Purchase Requests.
- Records Bids and quotation attachments.
- Selects Line Awards with reasons.
- Creates grouped Purchase Orders.
- Performs controlled Storage and Currently In Use movements.

Rename all visible Purchase Request Manager labels, errors, help text, and demo persona references to Procurement and Inventory Officer. Existing external XML identifiers may remain internally when changing them would make module upgrades unsafe, but they must not leak into business-facing language.

Server-side checks must enforce every authority rule; hidden buttons alone are insufficient.

## Notifications

- A due Running Hours threshold assigns one deduplicated activity to the responsible Maintenance user or team.
- Submitting a Purchase Request assigns one actionable review activity to the configured Procurement and Inventory Officer.
- Approving, rejecting, awarding, resetting an award, and creating Purchase Orders posts traceable chatter entries.
- Email delivery is not required for the local MVP; Odoo inbox/activity notifications are authoritative.

## Demo data

Seed a deterministic scenario matching the PM example:

- Product A: Bidder 1 and Bidder 2 quote; Bidder 1 wins.
- Product B: Bidder 1 and Bidder 3 quote; Bidder 1 wins.
- Product C: Bidder 3 quotes and wins.
- Purchase Order for Bidder 1 contains Products A and B.
- Purchase Order for Bidder 3 contains Product C.

Also seed:

- one Equipment item approaching its service interval;
- at least two historical Running Hour Readings;
- one due Maintenance activity;
- one equipment-linked Purchase Request visible from the map;
- representative Storage and Currently In Use records.

## Upgrade and migration

- Preserve existing Purchase Requests and completed standard Purchase Orders.
- Convert an open legacy preferred-vendor request into a single received Bid only when the mapping is unambiguous; otherwise leave it for manual review.
- Replace the singular Purchase Order link with a multi-order relationship without deleting the old order.
- Preserve done legacy one-step Inventory Issue stock movements and classify them as historical consumed issues.
- Create Currently In Use records only from new tugboat issues or from facts that can be proven by existing stock moves; do not invent onboard balances.
- Update `docs/custom-models.md`, implementation status, project requirements, manifests, security access, and shared Docker/demo installation in the implementation change.

## Verification

### Automated

- Running Hour Readings preserve history, reject invalid reductions, compute current hours, and create one due activity without duplicates.
- A submitted Purchase Request notifies the configured Procurement and Inventory Officer.
- Bidders may quote different subsets of request lines.
- One line cannot have multiple winners or a winning quote for less than its full quantity.
- An award requires a reason and cannot target an unquoted line.
- Three product-level awards across two suppliers create exactly two standard Purchase Orders with the correct lines.
- Repeating Purchase Order creation creates no duplicates.
- Losing Bids remain visible and immutable as award history.
- Inventory Issue creates a done movement from Storage to the tugboat location.
- Currently In Use reconciles with tugboat stock movements and closes only through return,
  consumption, or disposal; Technical Removal does not close it.
- Procurement users cannot bypass stock moves or alter historical done movements.
- Non-procurement map users cannot receive protected Bid prices or attachments from the server payload.

### Integrated Docker check

- Install or upgrade the affected Odoo 19 modules through the shared Docker setup.
- Run focused module tests for Maintenance, Inventory, Purchase Request, AIS, and demo reconciliation.
- Run `python3 scripts/verify_procurement_upgrade.py` from `sedar-new/` to verify the agreed
  pre-procurement legacy base in an isolated Compose project. The verifier snapshots legacy
  request/order/receipt/bill/issue/stock-move/line/lot facts, installs and upgrades a separate clean
  candidate database, upgrades the legacy database twice with the exact shared module list, checks
  the stable PM record set and A/B-versus-C order allocation after every candidate pass, and retains
  its isolated databases, filestore, JSON report, and logs on failure.
- Exercise the PM example through Purchase Request, Bid comparison, Line Awards, two Purchase Orders, receipt, Storage, issue, and Currently In Use.
- Open the fleet map, select the tugboat and Equipment, and verify active/history procurement behavior.
- Verify the Procurement navigation and responsive map/detail layout at 1440×900 and 390×844.
- Inspect the valid Equipment-detail JSON-RPC response as a restricted AIS/Maintenance-only user:
  access remains `limited`, while commercial identities, prices, terms, awards, suppliers, and
  quotation attachments are absent recursively. Direct Bid and attachment reads remain denied.

## Out of scope

- Supplier self-service portal or direct supplier logins
- Procurement of labor, inspections, overhaul, or repair services
- Automatic purchasing from Running Hours or reorder thresholds
- Automatic lowest-price selection or weighted scoring
- Splitting one request line's quantity across Bidders
- Multi-currency Bid normalization
- Separate Purchase Request Manager or second-person award approval
- Supplier qualification and performance scoring beyond existing partner data
- Live AIS/GPS integration

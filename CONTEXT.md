# SEDAR Marine Services

This glossary defines the shared business language for SEDAR's client-to-tugboat workflow.

## Language

**Demo Persona**:
A named user representing one department or an explicitly combined set of responsibilities during the demonstration.
_Avoid_: Test user, production role

**Demo Access Override**:
A temporary demonstration rule granting every internal employee Demo Persona all SEDAR and required Odoo manager permissions. Customer, applicant, and other portal accounts remain restricted; role-scoped employee permissions must replace this override after the demonstration.
_Avoid_: Production access policy, portal access

**Procurement and Inventory Officer**:
The employee responsible for reviewing Purchase Requests, recording Bids, selecting justified Line Awards, creating Purchase Orders, and performing controlled inventory work. It is one combined company role for the current scope.
_Avoid_: Purchase Request Manager, Procurement Manager

**Service Order**:
A client's request for one billable tug assist or move at one terminal. The team may also call it a Job Order; both names refer to the same record. A request containing multiple moves is represented by multiple Service Orders for the MVP.
_Also known as_: Job Order, Service Request (in customer-facing and Marketing language)

**Marine Operation**:
The execution record for a Ready Service Order. It records what happened while the requested work was performed, including the participating tugboats and crew, execution events, delays, completion evidence, and operational history. One Marine Operation is created automatically for each Ready Service Order. Its overall time spans from the earliest participating tug's actual start to the latest participating tug's actual end.
_Avoid_: Service Order, invoice

**Terminal**:
The specific operating location where a tug assist or move is performed and a dimension used to select the applicable Client Tariff.
_Avoid_: Port when a more specific location is known

**Tug Completion**:
A Tug Master's declaration that their assigned tugboat has finished its part of the requested work. The Tug Master records actual start when work begins, then actual end and a completion note when submitting completion; supporting evidence is optional for the MVP.
_Avoid_: Job done, operation done

**Service Completion**:
The point at which every active tug assignment for a Service Order has a Tug Completion. Service Completion is the business event that makes the whole completed service eligible for billing.
_Avoid_: Partial completion

**Actual Service Time**:
The elapsed time between the actual start and actual end recorded for a tug assignment. It is the billable quantity for time-based tariffs; estimated time is used only for planning and quotation.
_Avoid_: Estimated duration, planned duration

**Tug-Hour**:
One tugboat's Actual Service Time measured in hours. For a multi-tug Service Order, total tug-hours are the sum of each tugboat's Actual Service Time, even when the tugboats normally work in tandem.
_Avoid_: Service elapsed time

**Billing Review**:
The Finance review that begins after Service Completion and verifies the customer, applicable tariff, actual billable quantity, and adjustments before a draft invoice is created.
_Avoid_: Automatic invoicing

**Billing Adjustment**:
A Finance-entered charge or deduction outside the base tariff, recorded with a description, quantity, rate, and reason. Adjustment formulas remain manual until SEDAR provides confirmed rules.
_Avoid_: Automatic surcharge

**Client Tariff**:
An effective-dated, client-specific rate agreement used to calculate the base charge for a Service Order. Accounting Managers control approval; an approved tariff is preserved and later rate changes create a new version. Mock Client Tariffs stand in for SEDAR's real agreements during the MVP.
_Avoid_: Standard rate, invented rate

**Confirmed Rate**:
The Client Tariff rate selected using the scheduled service date and frozen when the client confirms the Service Order. Billing applies actual quantities to this rate; a schedule change into another tariff period requires Finance review rather than a silent rate change.
_Avoid_: Live billing-date rate

**Pricing Exception**:
A Billing Review state caused by the absence of a matching approved Client Tariff. It blocks invoice creation until tariff coverage is added.
_Avoid_: Manual base rate

**Billing Status**:
The financial progress of a completed Service Order through Billing Review, draft invoicing, invoicing, and payment. It remains separate from operational completion so an unpaid invoice does not make finished tug work appear unfinished.
_Avoid_: Operational status

**Customer Payment**:
Client funds recorded against a posted customer invoice with the receiving bank journal, date, amount, invoice reference, and optional deposit proof. Full bank-statement reconciliation remains outside the MVP.
_Avoid_: Invoice, revenue

**Completion Return**:
A Finance request for the Tug Master to correct a submitted Tug Completion, including a mandatory reason. Finance does not directly rewrite the Tug Master's operational record.
_Avoid_: Finance correction, silent edit

**Tug Master**:
The crew member with command responsibility for an assigned tugboat and authority to declare its work complete.
_Avoid_: Captain, skipper

**Dispatch Readiness Gate**:
An automated decision that allows a Service Order to proceed to execution only when its assigned tugboat, crew, and required inventory are ready. It is a system control, not a human approval role.
_Avoid_: Dispatch Manager approval

**Equipment**:
An individually tracked machine, system, or component installed on a tugboat, such as a main engine, generator, or pump. It has its own maintenance identity and may have running-hour readings.
_Avoid_: Item Type, inventory item, spare part, consumable

**Replacement Equipment**:
A complete physical unit procured to replace or add Equipment on a tugboat. It becomes tracked Equipment only when it is installed.
_Avoid_: Spare part, repair service, installed Equipment

**Running Hours**:
The cumulative operating time recorded by an Equipment hour meter. It is a maintenance reading, not the duration of a trip, Service Order, or Marine Operation.
_Avoid_: Runtime, Actual Service Time, job duration

**Running Hour Reading**:
A dated, attributable observation of an Equipment hour meter. Readings form an audit history, and the latest valid reading provides the Equipment's current Running Hours.
_Avoid_: Editable running-hours total, Actual Service Time

**Inventory Readiness Confirmation**:
A historical manual confirmation by an authorized Operations user that the inventory required by a Service Order was available for execution. Stock-backed Inventory Requirements now provide the normal readiness truth; the confirmer and confirmation time remain for older records without generated requirements.
_Avoid_: Automated inventory check

**Inventory Check**:
A Procurement review of a Service Order's stock-backed Inventory Requirements and related Item Types. The system determines Ready or Shortage from stock facts; the review is not a manual approval or readiness confirmation.
_Avoid_: Inventory approval, manual readiness gate

**Item Type**:
A stock product identified by one SEDAR Item Code and tracked as a quantity by location. It represents a kind of fuel, lubricant, spare part, or consumable rather than an individual physical unit.
_Avoid_: Serialized unit, individual item

**SEDAR Item Code**:
SEDAR's unique internal identifier for an Item Type. It becomes immutable after the Item Type has a stock transaction.
_Avoid_: Manufacturer Part Number, serial number

**Manufacturer Part Number**:
The item reference assigned by the manufacturer and printed on the item, packaging, or manufacturer documentation. It is searchable but is separate from the SEDAR Item Code and need not be globally unique.
_Avoid_: SEDAR Item Code

**Available to Issue**:
The physical quantity at the warehouse stock location minus quantities reserved there. It excludes stock at child or tug locations, damaged stock, and quantities not yet received.
_Avoid_: Company-wide stock, forecast stock

**Storage**:
Physical Inventory Items held at a warehouse stock location and available for reservation or issue. It excludes goods already assigned to or installed on tugboats.
_Avoid_: Currently In Use, company-wide stock

**Currently In Use**:
Physical goods held at a named tugboat's stock location and not yet returned, consumed, or disposed. It includes technically removed Equipment awaiting physical disposition and identifies the tugboat, related Equipment when applicable, quantity, and issue or installation date.
_Avoid_: Storage, consumed inventory, equipment procurement request

**Technical Removal**:
The audited uninstall of Replacement Equipment from its operating context while the physical unit remains held at the tugboat's stock location pending disposition. It preserves Equipment identity and Running Hour history and does not itself change stock quantity or location.
_Avoid_: Return to Storage, consumption, disposal, stock removal

**Inventory Disposition**:
The controlled physical return, consumption, or disposal that moves goods out of a tugboat's stock location and reduces their open Inventory Lifecycle quantity.
_Avoid_: Technical Removal, direct quantity adjustment

**Reorder Point**:
The manually maintained Available-to-Issue threshold at or below which an Item Type is Low Stock. Automatic purchasing is outside the initial Inventory Check demo.
_Avoid_: Purchase Request, automatic replenishment

**Tug Compatibility**:
The rule that an Item Type is either fleet-wide or restricted to one or more explicitly selected tugboats. An incompatible Item Type cannot be issued to a tugboat.
_Avoid_: Tug ownership

**Inventory Issue**:
An immutable, audited release of an Item Type from Storage to a named tugboat for a stated purpose. The goods remain traceable as Currently In Use until a later Inventory Disposition is recorded.
_Avoid_: Stock adjustment, immediate consumption

**Bidder**:
A supplier that has submitted a priced offer in response to a specific procurement request. Supplier registration or eligibility alone does not make a supplier a Bidder.
_Avoid_: Preferred Vendor, supplier directory, eligible supplier

**Bid**:
A supplier's priced offer for one or more product lines in a specific Purchase Request. Different Bidders may quote different subsets of the requested products.
_Avoid_: Request for Quotation, Purchase Order

**Bidder List**:
The Procurement workspace listing Bid headers. Each row represents one Bid for one Purchase Request and one supplier; it is not a supplier-directory record.
_Avoid_: Supplier directory, one row per supplier

**Line Award**:
Procurement's justified selection of one Bidder to supply the full quantity of a product line in a Purchase Request after comparing commercial terms. A line is not split between Bidders; awarded lines are grouped by winning Bidder for ordering.
_Avoid_: Whole-request award, Bid, supplier eligibility

**Purchase Order**:
The order issued to one winning supplier for the product lines awarded to that supplier. One Purchase Request may produce multiple Purchase Orders when different Bidders win different lines.
_Avoid_: Procurement Order, Bid, Purchase Request

**Purchase Request**:
An internal request asking Procurement to source physical Inventory Items, tugboat spare parts, or Replacement Equipment for a confirmed need. It excludes labor and external maintenance services and is not a Bid, Request for Quotation, or Purchase Order.
_Avoid_: Bid, Request for Quotation, Purchase Order, service request

**Simulated AIS Feed**:
A clearly labeled demonstration-only stream of fictional tugboat positions used to present fleet
monitoring without claiming a live AIS or GPS connection. Tugboat, crew, operation, maintenance,
and dry-dock facts still come from their owning Odoo records; only geographic reports and movement
between fictional waypoints are simulated.
_Avoid_: Live AIS, live GPS, navigational evidence

# Automate Service Order readiness and completion handoff

SEDAR treats Service Order and Job Order as the same client-request record. The system, rather than a human Dispatcher or Dispatch Manager, decides readiness from tugboat, crew, and inventory readiness; creates one awaiting-start Marine Operation when the order becomes Ready; derives operation timing and completion from the participating Tug Masters' actual start, actual end, and completion declarations; and sends the completed order to Finance Billing Review automatically. For the MVP, inventory readiness is a manual, audited Operations confirmation explicitly intended to be replaced by the future Inventory module.

## Status

Accepted

## Consequences

- Readiness automation does not claim that physical work has begun; a Tug Master's actual start commences execution.
- Every active tug must submit completion before the Marine Operation and Service Order complete.
- Returning a Tug Completion before invoicing reopens operational completion and removes the order from Billing Review.
- The temporary inventory confirmation must be cleared when relevant Service Order requirements change.
- Finance consumes the completed operational handoff and remains unable to declare operational readiness or completion.

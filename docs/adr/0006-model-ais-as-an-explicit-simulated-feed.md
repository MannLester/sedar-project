# Model AIS as an explicit simulated feed

## Status

Accepted

## Context

The demonstration requirements call for a visible AIS/GPS integration or mock feed, while no live
provider, data contract, credentials, polling interval, or retention policy has been approved by
SEDAR. A presentation that resembles live tracking without identifying its source would be
misleading. Depending on public map tiles would also make the local Docker demonstration fragile.

## Decision

The demonstration uses an explicitly labeled simulated AIS feed. `sedar.ais.position` stores one
current fictional report per tugboat, and a client action renders those reports on an offline-safe
Batangas Bay operations chart. The simulation may advance through fictional waypoints and animate
markers in the browser, but every screen and source record identifies the data as simulated.

The current-position model is the adapter boundary for a future live provider. A production adapter
may update the same normalized position fields after SEDAR approves a provider and integration
contract; it must preserve provider identity, source timestamps, error state, and position history.

## Consequences

- The client demo works without Google Maps keys, internet access, or an AIS subscription.
- Tugboat, crew, Marine Operation, maintenance, and dry-dock facts continue to come from their
  authoritative Odoo models; only location reports are simulated.
- Simulated records cannot be represented as navigational evidence or production vessel tracking.
- Live AIS history, geofencing, alerts, provider monitoring, and retention remain future work.

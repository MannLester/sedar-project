# Marketing UI parity TODO

The current `sedar_marketing` addon adapts the reference application to native Odoo views and workflows. Do not treat it as a one-to-one frontend port.

Reference:

- https://sedar-layout.vercel.app/marketing/dashboard
- https://github.com/EdrianHernandez/sedar-layout

## Deferred work

- Audit every reference route, component, state, empty state, dialog, drawer, filter, and responsive layout against Odoo.
- Match the reference visual system where native Odoo behavior is not sufficient.
- Build the reference-style contact create, view, and edit experience.
- Build the appointment day drawer and matching schedule, reschedule, cancellation, no-show, and follow-up interactions.
- Match quotation and contract confirmation dialogs, revision history, and status presentation.
- Complete document-request, version-history, visibility, archive, and restore interface parity.
- Match Activity Log timeline and table switching, filters, restricted-field presentation, and export controls.
- Verify control visibility and read-only behavior for every Marketing role and source department.
- Add representative quotations, contracts, appointments, documents, notes, and activity records to the demo fixture.
- Run desktop and mobile visual regression checks before calling the frontend a one-to-one port.

This work is intentionally deferred. The current implementation remains the functional Odoo baseline.

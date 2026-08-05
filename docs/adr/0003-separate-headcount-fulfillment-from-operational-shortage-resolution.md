# Separate headcount fulfillment from operational shortage resolution

## Status

Accepted

## Context

The recruitment demonstration links a Service Order crew shortage to a manpower request, vacancy,
application, offer, ADM-5 requirements, and employee creation. The earlier implementation marked the
original crew shortage resolved when HR opened the vacancy. That made the operational record look
fixed before SEDAR had hired anyone, onboarded the person as marine crew, verified credentials, or
assigned a concrete replacement.

## Decision

Opening a vacancy fulfills only the HR publication step. It does not resolve the original operational
crew shortage.

An applicant-to-employee conversion may fulfill the approved headcount demand for the linked vacancy
and manpower request. It still does not resolve the original Service Order shortage. A Service Order
shortage is resolved only by a concrete operational outcome, such as assigning a qualified replacement,
rescheduling the service, cancelling the need, restoring the unavailable crew member, or another
explicit crewing action.

## Consequences

- Vacancy and manpower status reflect HR headcount fulfillment.
- Crew shortage status remains owned by Operations and Crewing.
- Marine hires must pass a later crewing onboarding and deployment-eligibility workflow before they
  can be treated as operationally available.
- Dashboards may show both facts at the same time: the vacancy can be filled while the original
  operational shortage remains unresolved.

# SEDAR Repository Agent Instructions

These instructions apply to every agent working anywhere in this repository.

## Required context

Before planning, implementing, reviewing, or changing behavior:

1. Read the root `CONTEXT.md` completely.
2. Read the accepted ADRs in `docs/adr/` that relate to the task. For work involving service completion, billing, invoicing, or accounting, `docs/adr/0001-build-service-order-billing-on-odoo-accounting.md` is required reading.
3. Inspect the current code and module manifests. The glossary defines the shared language, ADRs define accepted architectural constraints, and the code defines current behavior.
4. Treat `sedar-new/` as the active Odoo 19 and Docker implementation unless the user explicitly asks about the legacy `odoo/` tree.
5. Read `docs/custom-models.md` before changing an Odoo model covered by that reference.

Do not silently proceed when the request, code, glossary, and an accepted ADR disagree. State the mismatch and confirm which source should change.

## Domain language

- Use the canonical terms and meanings from `CONTEXT.md` in plans, code, model names, UI copy, tests, and documentation.
- Keep `CONTEXT.md` as a glossary. Add or revise a term only after its meaning is agreed; do not put implementation plans or architecture decisions there.
- If a task introduces an unclear business term or changes an existing meaning, resolve that language before implementation.

## Architecture decisions

- Accepted ADRs are repository constraints, not optional background material.
- Do not overwrite or quietly contradict an accepted ADR. When a decision changes, create the next numbered ADR and mark which earlier ADR it supersedes.
- Create an ADR only for a consequential decision with a real tradeoff that would be costly or surprising to reverse. Keep routine implementation details in code or normal documentation.
- Preserve the boundary in ADR-0001: SEDAR modules own the marine completion and billing handoff workflow; Odoo Accounting owns the accounting ledger and standard accounting lifecycle.

## Custom model documentation

- Every new Odoo model and every field added to an inherited model must be documented in `docs/custom-models.md`.
- State the technical model and field names, field types, relationships, ownership, workflow purpose, and important access or validation rules.
- Update the documentation in the same change as the model. Removing or changing a field requires updating its documented contract as well.
- Method-only model extensions must be recorded when they change business workflow, security, accounting behavior, or demo bootstrap behavior.

## Planning with `grill-with-docs`

When the user asks to plan or stress-test a feature with `grill-with-docs`:

1. Read `CONTEXT.md` and the relevant ADRs first.
2. Ask one focused question at a time and challenge vague assumptions or missing edge cases.
3. Do not implement until the user confirms the resulting plan.
4. Record agreed terminology in `CONTEXT.md` and qualifying architecture decisions in a numbered ADR as the discussion progresses.
5. Keep implementation details in the implementation plan, not in the glossary.

## Verification

For implementation work, verify the affected Odoo 19 modules and their Docker installation or upgrade path. New required custom modules must be installed by the shared Docker setup so another team member receives the same application, UI, and seed-data behavior after following the repository instructions.

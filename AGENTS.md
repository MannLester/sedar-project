# SEDAR Repository Agent Instructions

These instructions apply to every agent working anywhere in this repository.

## Required context

Before planning, implementing, reviewing, or changing behavior:

1. Read the root `CONTEXT.md` completely.
2. Read the accepted ADRs in `docs/adr/` that relate to the task; `docs/adr/README.md` says which to read for what. For work involving service completion, billing, invoicing, or accounting, `docs/adr/0001-build-service-order-billing-on-odoo-accounting.md` is required reading. For any change that crosses addons or adds an addon, `docs/adr/0011-enforce-deep-addon-boundaries.md` is required reading.
3. Inspect the current code and module manifests. The glossary defines the shared language, ADRs define accepted architectural constraints, and the code defines current behavior. `docs/module-map.md` shows which addon belongs to which domain.
4. Treat `sedar-new/` as the active Odoo 19 and Docker implementation. The legacy `odoo/` tree and `docs/archive/` are reference only; do not change them unless the user explicitly asks.
5. Read `docs/custom-models.md` before changing an Odoo model covered by that reference.

Do not silently proceed when the request, code, glossary, and an accepted ADR disagree. State the mismatch and confirm which source should change.

## Domain language

- Use the canonical terms and meanings from `CONTEXT.md` in plans, code, model names, UI copy, tests, and documentation.
- Keep `CONTEXT.md` as a glossary. Add or revise a term only after its meaning is agreed; do not put implementation plans or architecture decisions there.
- If a task introduces an unclear business term or changes an existing meaning, resolve that language before implementation.

## Architecture decisions

- Accepted ADRs are repository constraints, not optional background material.
- Do not overwrite or quietly contradict an accepted ADR. When a decision changes, create the next numbered ADR, mark which earlier ADR it supersedes, and update `docs/adr/README.md`.
- Create an ADR only for a consequential decision with a real tradeoff that would be costly or surprising to reverse. Keep routine implementation details in code or normal documentation.
- Preserve the boundary in ADR-0001: SEDAR modules own the marine completion and billing handoff workflow; Odoo Accounting owns the accounting ledger and standard accounting lifecycle.

## Deep addon modules

Each addon is a deep module: a small declared public surface in front of a larger hidden implementation (ADR-0011). Rules:

- Declare what other addons may use in `sedar-new/architecture/boundaries.toml`. Every addon belongs to exactly one domain there.
- Reach another addon's model only if its owner lists it under `[public_models]` and your manifest depends on that owner. Do not call, override-and-call, or copy another addon's `_private` methods; add a public method on the owning addon instead.
- A method that other addons call is public by name and decorated with `@api.private` so Odoo does not expose it over RPC. Buttons and RPC actions stay public without `@api.private` and enforce their own access rules.
- Prefer a few verbs on the owning addon (`sync_automated_readiness`, `create_portal_event`) over exposing more models, fields, or helpers.
- Production addons must not depend on, import from, or reference data of demonstration addons. Seed fixtures in the `demo` domain.
- Keep new logic inside the addon that owns the business concept. If a change needs edits in three addons, first ask whether one addon should own a new public method.
- Never add an entry to `architecture/baseline.json` or a `noqa` pragma to make a check pass. Fix the cause. The baseline may only shrink; if you fix a baselined item, remove it with `make baseline`.

## Code rules

- No comments in Python or XML. Express intent through names, small functions, a short docstring on a public method, `docs/`, or an ADR. Only shebang and `noqa`/`pylint:`/`type:` pragmas are allowed.
- Keep Python files at 400 lines or fewer and XML files at 500 lines or fewer; split by aggregate or workflow when a file grows. Keep functions within the Ruff limits in `sedar-new/pyproject.toml` (complexity 10, 8 arguments, 50 statements).
- Every new Odoo model needs an access row in `security/ir.model.access.csv`, company-aware record rules when it belongs to a Service Order aggregate (ADR-0009), and every file the manifest must load listed in `__manifest__.py`.
- Inventory movement goes through standard Odoo stock moves (ADR-0004). Do not write `stock.quant` directly outside create-once fixture seeding.
- Do not add `sudo()` unless the code needs to cross an access rule, and then keep an explicit company predicate on the query.
- Add or update tests in the addon's `tests/` directory with every behavior change.

## Custom model documentation

- Every new Odoo model and every field added to an inherited model must be documented in `docs/custom-models.md`.
- State the technical model and field names, field types, relationships, ownership, workflow purpose, and important access or validation rules.
- Update the documentation in the same change as the model. Removing or changing a field requires updating its documented contract as well.
- Method-only model extensions must be recorded when they change business workflow, security, accounting behavior, or demo bootstrap behavior. Public cross-addon methods are listed under "Cross-addon public methods".
- `make check` fails on a new model or inherited field missing from the document.

## Verification

Run these from `sedar-new/` before reporting work done. Fix every failure you caused; do not report success on a failing check.

| Command | Purpose |
| --- | --- |
| `make check` | All static checks: Ruff, boundaries, comments, file size, XML, manifests, access rules, model documentation, check-script tests |
| `make test M="<addon> [<addon> ...]"` | Run those addons' Odoo tests in a disposable database |
| `make install` | Install every SEDAR module into a fresh database to prove a clean install |
| `make shell` | Odoo shell on the seeded database to try business methods |
| `make smoke` | Headless browser walk through the Service Order flow against a running server |
| `make baseline` | Rewrite the legacy-violation baseline after you fixed baselined items |

- `make test` and `make install` use Docker when it is available and otherwise the native Odoo setup (`make native-setup` once). Cloud agent sessions have no Docker; use the native path.
- Run the tests of every addon you changed and of every addon that depends on it. For changes that cross addons, run `make install` as well.
- For implementation work, also verify the Docker installation or upgrade path when Docker is available. New required custom modules must be installed by the shared Docker setup so another team member receives the same application, UI, and seed-data behavior after following the repository instructions. Add new modules to `SEDAR_MODULES` in `sedar-new/docker-compose.yml`.
- CI runs the same static checks and the native install and tests on every push and pull request.

## Planning with `grill-with-docs`

`grill-with-docs` comes from Matt Pocock's public skills repository:
https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs

If the skill is not installed in the current agent environment, do not assume it is locally available or skip the planning discipline. Read the upstream instructions when network access permits; otherwise follow the repository workflow below as the required fallback.

When the user asks to plan or stress-test a feature with `grill-with-docs`:

1. Read `CONTEXT.md` and the relevant ADRs first.
2. Ask one focused question at a time and challenge vague assumptions or missing edge cases.
3. Do not implement until the user confirms the resulting plan.
4. Record agreed terminology in `CONTEXT.md` and qualifying architecture decisions in a numbered ADR as the discussion progresses.
5. Keep implementation details in the implementation plan, not in the glossary.

## Working rules

- Develop on the branch the task names. Do not push to `main`. Do not open a pull request unless asked.
- Never commit `.local/`, `.env*`, database dumps, or credentials. The demo credentials in the repository are local fixtures, not secrets to reuse.
- Do not weaken a check, lower a limit, or widen the baseline without the user's explicit instruction.
- When a task needs a decision the user has not made (new business term, ADR change, access policy), stop and ask rather than choosing silently.

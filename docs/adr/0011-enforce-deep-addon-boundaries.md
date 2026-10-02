# Enforce deep addon boundaries

## Status

Accepted

## Context

Odoo does not hide implementation. Every field and method on a model is reachable from any
addon, and `_inherit` lets any addon change any model. SEDAR's 29 addons had grown to depend on
each other's internals: addons called private methods of other addons (for example
`orders._compute_readiness()` from Maintenance and Inventory), production addons depended on
demonstration addons, and addons read each other's models freely through `env[...]`. A change
inside one addon could therefore break another without any signal, and reviewers could not tell
which parts of an addon other addons were allowed to rely on.

## Decision

Each addon is a deep module: a small, declared public surface in front of a larger hidden
implementation.

- An addon's public surface is the set of models other addons may reach, declared under
  `[public_models]` in `sedar-new/architecture/boundaries.toml`, plus the public methods on
  those models.
- Another addon may reach a model through `env[...]` only when its owner declared it public and
  the caller's manifest depends on the owner, directly or transitively.
- Every addon is assigned to exactly one domain (`marine`, `people`, `supply`, `customer`,
  `platform`, `demo`) in the same file. Addon folders under `custom-addons/` mirror the domain.
- A method that other addons call is public by name and decorated with `@api.private`, so it is
  not exposed through Odoo's RPC. Methods that start with `_` are internal to their addon and
  must not be called from another addon. Buttons and RPC actions stay public without
  `@api.private` and enforce their own access rules.
- Production addons never depend on, import from, or reference data of a demonstration addon.
  Demonstration addons may call internal methods because they bootstrap fixtures through the
  same handoffs as real users.
- Static checks in `sedar-new/scripts/check.py` enforce these rules. Violations that existed
  when the rules were adopted are recorded in `sedar-new/architecture/baseline.json`; any
  violation not in the baseline fails the check, and the baseline may only shrink.

## Considered options

- Rely on written convention alone. Rejected because the existing violations show convention
  does not hold across 29 addons and many authors, human or agent.
- Introduce a service-layer class per addon now. Rejected as a large rewrite with no immediate
  business value; declared public models and `@api.private` methods give the same boundary
  with the current model structure.
- Restructure all addons immediately. Rejected in favor of a ratchet that stops new violations
  and lets existing ones be removed as the code is touched.

## Consequences

- Cross-addon reach-ins fail the check and need either a public method on the owning addon or
  an explicit, reviewable addition to `boundaries.toml`.
- The checks are static (syntax tree only). They find `env["model"]`, `env.ref("addon.xmlid")`,
  `odoo.addons.*` imports, and calls to underscore methods defined in a dependency addon. They do
  not follow a method call through variables of unknown type, and they do not restrict public
  methods, so reviewers still judge whether a declared public surface is small and stable.
- Production hooks that seed demonstration records through soft `env.ref(..., raise_if_not_found=False)`
  references remain in the baseline until that seeding moves into demonstration addons.
- Public models are not a stability promise to portal or external users; they only describe what
  other SEDAR addons may rely on.

"""Enforce addon boundaries: declared public models, no private cross-addon calls, demo isolation."""

from __future__ import annotations

import ast
from collections import defaultdict

from .core import (
    Addon,
    Violation,
    discover_addons,
    load_boundaries,
    model_owners,
    parse_python,
    relative,
    transitive_depends,
)

NAME = "boundaries"
SEDAR_ADDON_PREFIX = "sedar_"


def _env_model_references(tree: ast.Module):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "env"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            yield node.slice.value, node.lineno


def _env_ref_modules(tree: ast.Module):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ref"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and "." in node.args[0].value
        ):
            yield node.args[0].value.split(".", 1)[0], node.args[0].value, node.lineno


def _addon_imports(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("odoo.addons."):
            yield node.module.split(".")[2], node.lineno


def _source_files(addon: Addon):
    return [p for p in addon.files("*.py") if "tests" not in p.parts and "migrations" not in p.parts]


def _private_method_definitions(addons: dict[str, Addon]) -> dict[str, set[str]]:
    definitions: dict[str, set[str]] = defaultdict(set)
    for addon in addons.values():
        for path in _source_files(addon):
            for node in ast.walk(parse_python(path)):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("_") and not node.name.startswith("__"):
                    definitions[node.name].add(addon.name)
    return definitions


def _is_foreign_receiver(receiver: ast.expr) -> bool:
    if isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"}:
        return False
    is_super = (
        isinstance(receiver, ast.Call)
        and isinstance(receiver.func, ast.Name)
        and receiver.func.id == "super"
    )
    return not is_super


def _enclosing_functions(tree: ast.Module) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                lookup[id(child)] = node.name
    return lookup


def _private_calls(tree: ast.Module):
    enclosing = _enclosing_functions(tree)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("_")
            and not node.func.attr.startswith("__")
            and _is_foreign_receiver(node.func.value)
        ):
            yield node.func.attr, node.lineno, enclosing.get(id(node), "<module>")


def _check_domains(addons: dict[str, Addon], config: dict) -> list[Violation]:
    violations = []
    assigned: dict[str, str] = {}
    for domain, members in config.get("domains", {}).items():
        for member in members:
            if member in assigned:
                violations.append(Violation(
                    NAME, f"domain-twice:{member}",
                    f"{member} is listed in domains '{assigned[member]}' and '{domain}'",
                ))
            assigned[member] = domain
    for name, addon in addons.items():
        if name not in assigned:
            violations.append(Violation(
                NAME, f"domain-missing:{name}",
                f"{name} is not assigned to a domain in architecture/boundaries.toml",
            ))
        elif addon.group and addon.group != assigned[name]:
            violations.append(Violation(
                NAME, f"domain-folder:{name}",
                f"{name} is in folder '{addon.group}' but assigned to domain '{assigned[name]}'",
            ))
    violations.extend(
        Violation(NAME, f"domain-unknown:{member}", f"boundaries.toml lists unknown addon {member}")
        for member in assigned
        if member not in addons
    )
    return violations


def _check_demo_isolation(addons: dict[str, Addon], config: dict) -> list[Violation]:
    demo = set(config.get("domains", {}).get("demo", []))
    return [
        Violation(
            NAME, f"demo-dependency:{addon.name}->{dep}",
            f"{addon.name} is not a demo addon but depends on demo addon {dep}; "
            "production addons must never depend on demo data",
        )
        for addon in addons.values()
        if addon.name not in demo
        for dep in addon.depends
        if dep in demo
    ]


def _check_model_references(addon, tree, file_key, context) -> list[Violation]:
    addons, owners, public, deps = context
    violations = []
    for model, line in _env_model_references(tree):
        owner = owners.get(model)
        if owner is None or owner == addon.name:
            continue
        if owner not in deps:
            violations.append(Violation(
                NAME, f"missing-dependency:{addon.name}:{model}",
                f"{file_key}:{line} uses {model} owned by {owner}, which {addon.name} does not depend on",
            ))
        elif model not in public.get(owner, []):
            violations.append(Violation(
                NAME, f"undeclared-model:{addon.name}:{model}",
                f"{file_key}:{line} reaches into {model}, which {owner} has not declared public; "
                "call a declared public model, or declare it under [public_models] in "
                "architecture/boundaries.toml",
            ))
    for module, line in _addon_imports(tree):
        if module.startswith(SEDAR_ADDON_PREFIX) and module != addon.name and module in addons and module not in deps:
            violations.append(Violation(
                NAME, f"missing-dependency:{addon.name}:import:{module}",
                f"{file_key}:{line} imports from {module}, which {addon.name} does not depend on",
            ))
    for module, xmlid, line in _env_ref_modules(tree):
        if module.startswith(SEDAR_ADDON_PREFIX) and module != addon.name and module in addons and module not in deps:
            violations.append(Violation(
                NAME, f"missing-dependency:{addon.name}:{xmlid}",
                f"{file_key}:{line} references {xmlid} from {module}, which {addon.name} does not depend on",
            ))
    return violations


def _check_private_calls(addon, tree, file_key, deps, definitions, allowed) -> list[Violation]:
    violations = []
    for method, line, function in _private_calls(tree):
        foreign = {d for d in definitions.get(method, set()) if d != addon.name and d in deps}
        if foreign and f"{addon.name}:{method}" not in allowed:
            violations.append(Violation(
                NAME, f"private-call:{file_key}:{function}:{method}",
                f"{file_key}:{line} calls private method {method} defined in {', '.join(sorted(foreign))}; "
                "expose a public method on the owning addon instead",
            ))
    return violations


def run() -> list[Violation]:
    addons = discover_addons()
    config = load_boundaries()
    owners = model_owners(addons)
    public = config.get("public_models", {})
    allowed = set(config.get("allowed_private_calls", []))
    demo = set(config.get("domains", {}).get("demo", []))
    definitions = _private_method_definitions(addons)
    violations = _check_domains(addons, config) + _check_demo_isolation(addons, config)
    for addon in addons.values():
        deps = transitive_depends(addons, addon.name)
        for path in _source_files(addon):
            tree = parse_python(path)
            file_key = relative(path)
            violations.extend(_check_model_references(addon, tree, file_key, (addons, owners, public, deps)))
            if addon.name not in demo:
                violations.extend(_check_private_calls(addon, tree, file_key, deps, definitions, allowed))
    return violations

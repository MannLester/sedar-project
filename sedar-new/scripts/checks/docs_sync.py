"""Require docs/custom-models.md to cover every custom model and every field added to a core model."""

from __future__ import annotations

import ast

from . import core
from .core import Violation, discover_addons, parse_python, relative

NAME = "docs-sync"


def _declared(cls: ast.ClassDef) -> tuple[str | None, list[str]]:
    name = None
    inherits: list[str] = []
    for stmt in cls.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            continue
        target = stmt.targets[0].id
        if target == "_name" and isinstance(stmt.value, ast.Constant):
            name = stmt.value.value
        elif target == "_inherit":
            if isinstance(stmt.value, ast.Constant):
                inherits = [stmt.value.value]
            elif isinstance(stmt.value, (ast.List, ast.Tuple)):
                inherits = [e.value for e in stmt.value.elts if isinstance(e, ast.Constant)]
    return name, inherits


def _added_fields(cls: ast.ClassDef) -> list[str]:
    fields = []
    for stmt in cls.body:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)
            and stmt.value.func.value.id == "fields"
        ):
            fields.append(stmt.targets[0].id)
    return fields


def run() -> list[Violation]:
    documentation = core.MODELS_DOC.read_text(encoding="utf-8")
    violations = []
    for addon in discover_addons().values():
        for path in addon.files("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            for node in ast.walk(parse_python(path)):
                if not isinstance(node, ast.ClassDef):
                    continue
                name, inherits = _declared(node)
                if name and f"`{name}`" not in documentation:
                    violations.append(Violation(
                        NAME, f"model:{name}",
                        f"{relative(path)} defines {name}, which is missing from docs/custom-models.md",
                    ))
                if name or not inherits or all(i.startswith("sedar.") for i in inherits):
                    continue
                violations.extend(
                    Violation(
                        NAME, f"field:{inherits[0]}.{field}",
                        f"{relative(path)} adds {field} to {inherits[0]}, which is missing from docs/custom-models.md",
                    )
                    for field in _added_fields(node)
                    if f"`{field}`" not in documentation
                )
    return violations

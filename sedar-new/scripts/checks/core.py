"""Shared discovery, parsing, and violation reporting for the static checks."""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADDONS_ROOT = PROJECT_ROOT / "custom-addons"
BOUNDARIES_FILE = PROJECT_ROOT / "architecture" / "boundaries.toml"
BASELINE_FILE = PROJECT_ROOT / "architecture" / "baseline.json"
MODELS_DOC = PROJECT_ROOT.parent / "docs" / "custom-models.md"
SKIPPED_PARTS = {"__pycache__", "node_modules", ".venv"}


@dataclass(frozen=True)
class Violation:
    check: str
    key: str
    message: str

    def render(self) -> str:
        return f"[{self.check}] {self.message}"


@dataclass
class Addon:
    name: str
    path: Path
    manifest: dict
    group: str
    models_owned: set[str] = field(default_factory=set)
    models_extended: set[str] = field(default_factory=set)

    @property
    def depends(self) -> list[str]:
        return list(self.manifest.get("depends", []))

    def files(self, pattern: str) -> list[Path]:
        return sorted(p for p in self.path.rglob(pattern) if not SKIPPED_PARTS & set(p.parts))


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def parse_python(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def discover_addons(root: Path | None = None) -> dict[str, Addon]:
    root = root or ADDONS_ROOT
    addons: dict[str, Addon] = {}
    for manifest_path in sorted(root.glob("**/__manifest__.py")):
        addon_dir = manifest_path.parent
        if SKIPPED_PARTS & set(addon_dir.parts):
            continue
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        parent = addon_dir.parent
        group = "" if parent == root else parent.name
        addon = Addon(addon_dir.name, addon_dir, manifest, group)
        _collect_models(addon)
        addons[addon.name] = addon
    return addons


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _class_model_declarations(cls: ast.ClassDef) -> tuple[str | None, list[str]]:
    name = None
    inherits: list[str] = []
    for stmt in cls.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id == "_name":
            name = _string_constant(stmt.value)
        elif target.id == "_inherit":
            single = _string_constant(stmt.value)
            if single:
                inherits = [single]
            elif isinstance(stmt.value, (ast.List, ast.Tuple)):
                inherits = [s for s in map(_string_constant, stmt.value.elts) if s]
    return name, inherits


def _collect_models(addon: Addon) -> None:
    for path in addon.files("*.py"):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        for node in ast.walk(parse_python(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            name, inherits = _class_model_declarations(node)
            if name:
                addon.models_owned.add(name)
            elif inherits:
                addon.models_extended.update(inherits)


def model_owners(addons: dict[str, Addon]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for addon in addons.values():
        for model in addon.models_owned:
            owners.setdefault(model, addon.name)
    return owners


def transitive_depends(addons: dict[str, Addon], name: str) -> set[str]:
    seen: set[str] = set()
    stack = list(addons[name].depends) if name in addons else []
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        if current in addons:
            stack.extend(addons[current].depends)
    return seen


def load_boundaries(path: Path | None = None) -> dict:
    with (path or BOUNDARIES_FILE).open("rb") as handle:
        return tomllib.load(handle)

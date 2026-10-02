"""Source hygiene: no comments, file size limits, XML well-formedness, manifests, access rules."""

from __future__ import annotations

import ast
import csv
import io
import re
import tokenize
import xml.etree.ElementTree as ET
from pathlib import Path

from . import core
from .core import (
    SKIPPED_PARTS,
    Violation,
    discover_addons,
    load_boundaries,
    parse_python,
    relative,
)

PRAGMA_RE = re.compile(r"^#\s*(noqa\b|pylint:|type:|-\*-|!)")
NOQA_RE = re.compile(r"^#\s*noqa\b")
XML_COMMENT_RE = re.compile(r"<!--")
DEFAULT_LIMITS = {"python_lines": 400, "xml_lines": 500}
REQUIRED_MANIFEST_KEYS = ("name", "version", "depends", "license", "installable")
DATA_DIRS = ("security", "views", "data", "report", "wizard")


def _python_files() -> list[Path]:
    roots = [core.ADDONS_ROOT, core.PROJECT_ROOT / "scripts"]
    return sorted(p for root in roots for p in root.rglob("*.py") if not SKIPPED_PARTS & set(p.parts))


def _xml_files() -> list[Path]:
    return sorted(p for p in core.ADDONS_ROOT.rglob("*.xml") if not SKIPPED_PARTS & set(p.parts))


def check_comments() -> list[Violation]:
    name = "comments"
    violations = []
    for path in _python_files():
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type == tokenize.COMMENT and not PRAGMA_RE.match(token.string):
                    violations.append(Violation(
                        name, f"{relative(path)}:{token.start[0]}",
                        f"{relative(path)}:{token.start[0]} has a comment; express intent through names, "
                        "a short docstring, docs/, or an ADR instead",
                    ))
    for path in _xml_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if XML_COMMENT_RE.search(line):
                violations.append(Violation(
                    name, f"{relative(path)}:{number}",
                    f"{relative(path)}:{number} has an XML comment; remove it or move the explanation to docs/",
                ))
    return violations


def check_pragmas() -> list[Violation]:
    name = "pragmas"
    violations = []
    for path in _python_files():
        with path.open("rb") as handle:
            count = sum(
                1 for token in tokenize.tokenize(handle.readline)
                if token.type == tokenize.COMMENT and NOQA_RE.match(token.string)
            )
        if count:
            violations.append(Violation(
                name, f"{relative(path)}:noqa:{count}",
                f"{relative(path)} has {count} noqa pragma(s); fix the lint finding instead of suppressing it",
            ))
    return violations


def check_sizes() -> list[Violation]:
    name = "file-size"
    limits = {**DEFAULT_LIMITS, **load_boundaries().get("limits", {})}
    violations = []
    for path in _python_files():
        if "tests" in path.parts:
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > limits["python_lines"]:
            violations.append(Violation(
                name, relative(path),
                f"{relative(path)} has {lines} lines (limit {limits['python_lines']}); split it by aggregate",
            ))
    for path in _xml_files():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > limits["xml_lines"]:
            violations.append(Violation(
                name, relative(path),
                f"{relative(path)} has {lines} lines (limit {limits['xml_lines']}); split views by model or workflow",
            ))
    return violations


def check_xml() -> list[Violation]:
    violations = []
    for path in _xml_files():
        try:
            ET.parse(path)
        except ET.ParseError as error:
            violations.append(Violation("xml", relative(path), f"{relative(path)} is not well-formed XML: {error}"))
    return violations


def _manifest_files(addon) -> list[str]:
    manifest = addon.manifest
    return list(manifest.get("data", [])) + list(manifest.get("demo", []))


def check_manifests() -> list[Violation]:
    name = "manifest"
    violations = []
    for addon in discover_addons().values():
        for key in REQUIRED_MANIFEST_KEYS:
            if key not in addon.manifest:
                violations.append(Violation(name, f"{addon.name}:key:{key}", f"{addon.name} manifest is missing '{key}'"))
        listed = set(_manifest_files(addon))
        for entry in listed:
            if not (addon.path / entry).exists():
                violations.append(Violation(name, f"{addon.name}:missing:{entry}", f"{addon.name} manifest lists missing file {entry}"))
        for directory in DATA_DIRS:
            for path in addon.files(f"{directory}/*"):
                relative_path = path.relative_to(addon.path).as_posix()
                if path.suffix in {".xml", ".csv"} and relative_path not in listed:
                    violations.append(Violation(
                        name, f"{addon.name}:unlisted:{relative_path}",
                        f"{addon.name}/{relative_path} is not listed in the manifest and will never load",
                    ))
    return violations


def _access_models(addon) -> set[str]:
    path = addon.path / "security" / "ir.model.access.csv"
    if not path.exists():
        return set()
    rows = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    return {row["model_id:id"].rsplit("model_", 1)[-1] for row in rows if row.get("model_id:id")}


def _model_kinds(addon) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for path in addon.files("models/*.py") + addon.files("wizard/*.py") + addon.files("wizards/*.py"):
        for node in ast.walk(parse_python(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            model_name = None
            kind = "model"
            for stmt in node.body:
                is_name_assignment = (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.targets[0].id == "_name"
                )
                if is_name_assignment:
                    model_name = stmt.value.value
            for base in node.bases:
                if isinstance(base, ast.Attribute) and base.attr in {"TransientModel", "AbstractModel"}:
                    kind = base.attr
            if model_name:
                kinds[model_name] = kind
    return kinds


def check_access() -> list[Violation]:
    name = "access"
    violations = []
    for addon in discover_addons().values():
        covered = _access_models(addon)
        for model, kind in _model_kinds(addon).items():
            if kind == "model" and model.replace(".", "_") not in covered:
                violations.append(Violation(
                    name, f"{addon.name}:{model}",
                    f"{addon.name} defines {model} without a row in security/ir.model.access.csv",
                ))
    return violations

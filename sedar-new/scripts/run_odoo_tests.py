#!/usr/bin/env python3
"""Run selected SEDAR Odoo tests in an isolated, disposable database."""

from __future__ import annotations

import argparse
import re
import secrets
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DATABASE_RE = re.compile(r"^sedar_test_[a-z0-9_]{12,40}$")
OWNERSHIP_MARKER_RE = re.compile(r"^sedar_runner_[0-9a-f]{32}$")
CONTAINER_OWNER_LABEL = "sedar.test-owner"
# A high, effectively non-binding PostgreSQL connection limit doubles as an atomic
# ownership marker because it is stored by the same CREATE DATABASE statement.
DATABASE_MARKER_MIN = 1_000_000_000
DATABASE_MARKER_SPAN = 1_000_000_000
MODULE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TAG_RE = re.compile(
    r"^(?P<sign>[+-]?)(?P<tag>\*|[A-Za-z0-9_]*)"
    r"(?:/(?P<module>[a-z][a-z0-9_]*))?"
    r"(?::(?P<test_class>[A-Za-z_][A-Za-z0-9_]*)?)?"
    r"(?:\.(?P<test_method>[A-Za-z_][A-Za-z0-9_]*))?$"
)


class RunnerError(RuntimeError):
    """Raised for invalid or unsafe runner input and state."""


class SignalInterrupt(Exception):
    def __init__(self, signum: int):
        self.signum = signum


@dataclass(frozen=True)
class RunResources:
    root: Path
    database: str
    container: str
    container_marker: str
    database_marker: int
    http_port: int


def _raise_signal(signum, _frame):
    raise SignalInterrupt(signum)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def generate_database_name() -> str:
    name = f"sedar_test_{secrets.token_hex(10)}"
    validate_database_name(name)
    return name


def generate_run_resources(root: Path) -> RunResources:
    database = generate_database_name()
    token = database.removeprefix("sedar_test_")
    return RunResources(
        root=root,
        database=database,
        container=f"sedar-odoo-test-{token}",
        container_marker=f"sedar_runner_{secrets.token_hex(16)}",
        database_marker=DATABASE_MARKER_MIN + secrets.randbelow(DATABASE_MARKER_SPAN),
        http_port=20000 + secrets.randbelow(20000),
    )


def validate_database_name(name: str) -> None:
    if len(name) > 63 or not DATABASE_RE.fullmatch(name):
        raise RunnerError("Refusing unsafe test database name.")


def available_modules(root: Path) -> set[str]:
    return {
        path.parent.name
        for path in (root / "custom-addons").glob("*/__manifest__.py")
        if path.is_file()
    }


def tested_modules(root: Path) -> list[str]:
    return sorted(
        path.parent.parent.name
        for path in (root / "custom-addons").glob("*/tests/test_*.py")
    )


def validate_modules(root: Path, modules: list[str]) -> list[str]:
    known = available_modules(root)
    selected = []
    for module in modules:
        if not MODULE_RE.fullmatch(module) or module not in known:
            raise RunnerError(f"Unknown or unsafe SEDAR module: {module!r}")
        if module not in selected:
            selected.append(module)
    return selected


def validate_test_tags(tags: str, selected_modules: set[str]) -> str:
    specs = [spec.strip() for spec in tags.split(",")]
    matches = [TAG_RE.fullmatch(spec) for spec in specs]
    if (
        not specs
        or any(not spec or not match for spec, match in zip(specs, matches))
        or any(match.group("sign") in {"+", "-"} and not match.group("tag") for match in matches)
        or any(not any(match.groupdict().values()) for match in matches)
    ):
        raise RunnerError("Test tags do not match Odoo's supported tag/module/class/method syntax.")
    tag_modules = {match.group("module") for match in matches if match.group("module")}
    unknown = tag_modules - selected_modules
    if unknown:
        raise RunnerError(f"Test tags reference modules not selected for installation: {sorted(unknown)}")
    return ",".join(specs)


def command_result(command: list[str], cwd: Path, quiet: bool = False) -> int:
    output = subprocess.DEVNULL if quiet else None
    return subprocess.run(
        command, cwd=cwd, check=False, stdout=output, stderr=output
    ).returncode


def command_output(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        command, cwd=cwd, check=False, capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip()


def _container_names(root: Path, container: str) -> tuple[int, set[str]]:
    status, output = command_output([
        "docker", "ps", "-a", "--filter", f"name=^/{container}$",
        "--format", "{{.Names}}",
    ], root)
    return status, set(output.splitlines())


def _container_marker(root: Path, container: str) -> tuple[int, str]:
    return command_output([
        "docker", "inspect", "--format",
        f'{{{{ index .Config.Labels "{CONTAINER_OWNER_LABEL}" }}}}', container,
    ], root)


def database_exists(root: Path, database: str) -> tuple[int, bool]:
    validate_database_name(database)
    status, output = command_output([
        "docker", "compose", "exec", "-T", "db", "psql", "--username", "odoo",
        "--dbname", "postgres", "--tuples-only", "--no-align",
        "--command", f"SELECT 1 FROM pg_database WHERE datname = '{database}';",
    ], root)
    return status, bool(output)


def database_has_marker(root: Path, database: str, marker: int) -> tuple[int, bool]:
    validate_database_name(database)
    if not DATABASE_MARKER_MIN <= marker < DATABASE_MARKER_MIN + DATABASE_MARKER_SPAN:
        raise RunnerError("Refusing unsafe database ownership marker.")
    status, output = command_output([
        "docker", "compose", "exec", "-T", "db", "psql", "--username", "odoo",
        "--dbname", "postgres", "--tuples-only", "--no-align",
        "--command", (
            "SELECT 1 FROM pg_database WHERE "
            f"datname = '{database}' AND "
            f"datconnlimit = {marker};"
        ),
    ], root)
    return status, bool(output)


def _cleanup_container(resources: RunResources) -> list[str]:
    errors = []
    inspect_status, containers = _container_names(resources.root, resources.container)
    if inspect_status:
        errors.append(f"Could not inspect test container {resources.container!r}.")
    elif resources.container in containers:
        marker_status, container_marker = _container_marker(
            resources.root, resources.container
        )
        if marker_status:
            errors.append(
                f"Could not inspect ownership of test container {resources.container!r}."
            )
        elif container_marker != resources.container_marker:
            errors.append(f"Retained unowned test container {resources.container!r}.")
        elif command_result(
            ["docker", "rm", "--force", resources.container], resources.root
        ):
            errors.append(f"Could not remove owned test container {resources.container!r}.")
        else:
            verify_status, remaining = _container_names(
                resources.root, resources.container
            )
            if verify_status or resources.container in remaining:
                errors.append(f"Test container still exists: {resources.container}.")
    return errors


def _cleanup_database(resources: RunResources) -> list[str]:
    errors = []
    marker_status, owns_database = database_has_marker(
        resources.root, resources.database, resources.database_marker
    )
    if marker_status:
        errors.append(
            f"Could not inspect ownership of test database {resources.database!r}."
        )
    elif owns_database:
        if command_result([
            "docker", "compose", "exec", "-T", "db", "dropdb", "--username", "odoo",
            "--if-exists", "--force", resources.database,
        ], resources.root):
            errors.append(f"Could not drop test database {resources.database!r}.")
        verify_status, remaining = database_exists(
            resources.root, resources.database
        )
        if verify_status:
            errors.append(
                f"Could not verify removal of test database {resources.database!r}."
            )
        elif remaining:
            errors.append(f"Test database still exists: {resources.database}.")
    return errors


def cleanup(resources: RunResources) -> list[str]:
    validate_database_name(resources.database)
    if not OWNERSHIP_MARKER_RE.fullmatch(resources.container_marker):
        raise RunnerError("Refusing unsafe container ownership marker.")
    return _cleanup_container(resources) + _cleanup_database(resources)


def run(root: Path, modules: list[str], tags: str | None = None) -> int:
    selected = validate_modules(root, modules or tested_modules(root))
    if not selected:
        raise RunnerError("No SEDAR test modules were found.")
    test_tags = validate_test_tags(
        tags or ",".join(f"/{module}" for module in selected), set(selected)
    )
    resources = generate_run_resources(root)
    install_modules = selected if modules else ["sedar_demo_suite"]
    primary_status = None
    primary_exception = False
    try:
        for command in (
            ["docker", "compose", "config", "--quiet"],
            ["docker", "compose", "up", "-d", "--wait", "db"],
        ):
            status = command_result(command, root)
            if status:
                primary_status = status
                return status
        status, exists = database_exists(root, resources.database)
        if status:
            primary_status = status
            return status
        if exists:
            raise RunnerError(
                f"Generated test database name already exists: {resources.database!r}."
            )
        status = command_result([
            "docker", "compose", "exec", "-T", "db", "psql", "--username", "odoo",
            "--dbname", "postgres", "--set", "ON_ERROR_STOP=1",
            "--command", (
                f"CREATE DATABASE {resources.database} OWNER odoo "
                f"CONNECTION LIMIT {resources.database_marker};"
            ),
        ], root)
        if status:
            primary_status = status
            return status
        status = command_result([
            "docker", "compose", "run", "--rm", "-T", "--name", resources.container,
            "--label", f"{CONTAINER_OWNER_LABEL}={resources.container_marker}", "odoo", "odoo",
            "-c", "/etc/odoo/odoo.conf", "--database", resources.database,
            "--db-filter", f"^{resources.database}$", "--init", ",".join(install_modules),
            "--test-tags", test_tags, "--stop-after-init", "--without-demo=true",
            "--http-interface", "127.0.0.1", "--http-port", str(resources.http_port),
            "--data-dir", "/tmp/sedar-odoo-test-data", "--max-cron-threads", "0",
        ], root)
        primary_status = status
        return status
    except BaseException:
        primary_exception = True
        raise
    finally:
        cleanup_errors = cleanup(resources)
        if cleanup_errors:
            message = "Isolated test cleanup failed: " + " ".join(cleanup_errors)
            if primary_exception or primary_status not in (None, 0):
                print(f"error: {message}", file=sys.stderr)
            else:
                raise RunnerError(message)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", action="append", default=[], help="Install and test one module; repeatable.")
    parser.add_argument(
        "--test-tags",
        help="Odoo tag/module/class/method selectors; any named module must also be selected.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    signal.signal(signal.SIGINT, _raise_signal)
    signal.signal(signal.SIGTERM, _raise_signal)
    try:
        return run(project_root(), args.module, args.test_tags)
    except (KeyboardInterrupt, SignalInterrupt) as error:
        signum = getattr(error, "signum", signal.SIGINT)
        return 128 + signum
    except RunnerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

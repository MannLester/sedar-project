#!/usr/bin/env python3
"""Run SEDAR on a native Odoo 19 checkout and local PostgreSQL, without Docker.

Used by agents and cloud sessions that cannot run Docker. Commands: setup, install, test, shell, run.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
ODOO_SRC = Path(os.environ.get("SEDAR_ODOO_SRC", LOCAL / "odoo19"))
VENV = Path(os.environ.get("SEDAR_VENV", LOCAL / "venv"))
LOG_DIR = LOCAL / "logs"
DB_ARGS = ["--db_host=localhost", "--db_user=odoo", "--db_password=odoo"]
SUMMARY_RE = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")
MODULE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
APT_PACKAGES = [
    "postgresql", "libpq-dev", "libldap2-dev", "libsasl2-dev", "libxml2-dev",
    "libxslt1-dev", "libjpeg-dev", "zlib1g-dev", "python3-dev", "build-essential",
]


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=False, **kwargs)


def python() -> str:
    return str(VENV / "bin" / "python")


def all_modules() -> str:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    match = re.search(r'SEDAR_MODULES="([^"]+)"', text)
    if not match:
        sys.exit("SEDAR_MODULES not found in docker-compose.yml")
    return match.group(1)


def addons_path() -> str:
    parents = {path.parent.parent for path in (ROOT / "custom-addons").glob("**/__manifest__.py")}
    paths = [ODOO_SRC / "odoo" / "addons", ODOO_SRC / "addons", *sorted(parents)]
    return ",".join(str(path) for path in paths)


def odoo_command(database: str, *extra: str, subcommand: str | None = None) -> list[str]:
    return [
        python(), str(ODOO_SRC / "odoo-bin"), *([subcommand] if subcommand else []),
        f"--addons-path={addons_path()}", *DB_ARGS,
        f"--data-dir={LOCAL / 'data'}", "-d", database, *extra,
    ]


def ensure_postgres() -> None:
    if run(["pg_isready", "-q"]).returncode != 0:
        run(["service", "postgresql", "start"])
    role_exists = run(
        ["su", "postgres", "-c", "psql -tAc \"select 1 from pg_roles where rolname='odoo'\""],
        capture_output=True, text=True,
    ).stdout.strip()
    if role_exists != "1":
        run(["su", "postgres", "-c", "psql -c \"CREATE ROLE odoo LOGIN SUPERUSER PASSWORD 'odoo'\""])


def drop_database(database: str) -> None:
    run(["dropdb", "-h", "localhost", "-U", "odoo", "--if-exists", database], env={**os.environ, "PGPASSWORD": "odoo"})


def database_exists(database: str) -> bool:
    result = run(
        ["psql", "-h", "localhost", "-U", "odoo", "-tAc", f"select 1 from pg_database where datname='{database}'", "postgres"],
        capture_output=True, text=True, env={**os.environ, "PGPASSWORD": "odoo"},
    )
    return result.stdout.strip() == "1"


def command_setup(_args) -> int:
    LOCAL.mkdir(exist_ok=True)
    if shutil.which("pg_ctl") is None and not list(Path("/usr/lib/postgresql").glob("*/bin/pg_ctl")):
        if os.geteuid() != 0:
            sys.exit(f"Install PostgreSQL and: {' '.join(APT_PACKAGES)}")
        run(["apt-get", "update", "-qq"])
        run(["apt-get", "install", "-y", "-qq", *APT_PACKAGES])
    if not ODOO_SRC.exists():
        run(["git", "clone", "--depth", "1", "--branch", "19.0", "https://github.com/odoo/odoo.git", str(ODOO_SRC)])
    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
        run([python(), "-m", "pip", "install", "-q", "-U", "pip", "wheel", "setuptools"])
        run([python(), "-m", "pip", "install", "-q", "-r", str(ODOO_SRC / "requirements.txt")])
    ensure_postgres()
    print(f"native Odoo ready: source {ODOO_SRC}, virtualenv {VENV}")
    return 0


def stream_to_log(command: list[str], log_name: str) -> tuple[int, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    with log_path.open("w", encoding="utf-8") as handle:
        return run(command, stdout=handle, stderr=subprocess.STDOUT).returncode, log_path


def log_problems(log_path: Path) -> list[str]:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line for line in lines if " ERROR " in line or " CRITICAL " in line or line.startswith("FAIL:")]


def command_install(args) -> int:
    ensure_postgres()
    if args.replace:
        drop_database(args.database)
    modules = args.module and ",".join(args.module) or all_modules()
    command = odoo_command(args.database, "-i", modules, "--without-demo=true", "--stop-after-init", "--no-http")
    code, log_path = stream_to_log(command, f"install-{args.database}.log")
    problems = log_problems(log_path)
    print(f"install {args.database}: exit {code}, {len(problems)} error line(s), log {log_path}")
    for line in problems[:10]:
        print(f"  {line[:200]}")
    return 1 if code or problems else 0


def validate_modules(modules: list[str]) -> None:
    for module in modules:
        if not MODULE_RE.match(module):
            sys.exit(f"invalid module name: {module}")


def command_test(args) -> int:
    ensure_postgres()
    validate_modules(args.module)
    database = f"sedar_test_{secrets.token_hex(6)}"
    tags = args.test_tags or ",".join(f"/{module}" for module in args.module)
    command = odoo_command(
        database, "-i", ",".join(args.module), "--test-enable", f"--test-tags={tags}",
        "--without-demo=true", "--stop-after-init", "--http-port=0",
    )
    try:
        code, log_path = stream_to_log(command, f"test-{database}.log")
    finally:
        drop_database(database)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    summaries = SUMMARY_RE.findall(text)
    failed = sum(int(f) + int(e) for f, e, _ in summaries)
    total = sum(int(t) for _, _, t in summaries)
    problems = log_problems(log_path)
    print(f"test {','.join(args.module)}: {total} tests, {failed} failed/error, log {log_path}")
    if failed or not summaries:
        for line in problems[:10]:
            print(f"  {line[:200]}")
    return 1 if code or failed or not summaries else 0


def command_shell(args) -> int:
    ensure_postgres()
    return run(odoo_command(args.database, "--no-http", subcommand="shell")).returncode


def command_run(args) -> int:
    ensure_postgres()
    command = odoo_command(args.database, f"--http-port={args.port}")
    os.execv(command[0], command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="install PostgreSQL, clone Odoo 19, create the virtualenv").set_defaults(handler=command_setup)
    install = commands.add_parser("install", help="install SEDAR modules into a database")
    install.add_argument("--database", default="sedar_dev")
    install.add_argument("--module", action="append", help="limit to these modules (default: all)")
    install.add_argument("--replace", action="store_true", help="drop the database first")
    install.set_defaults(handler=command_install)
    test = commands.add_parser("test", help="run module tests in a disposable database")
    test.add_argument("--module", action="append", required=True)
    test.add_argument("--test-tags")
    test.set_defaults(handler=command_test)
    shell = commands.add_parser("shell", help="open an Odoo shell on a database")
    shell.add_argument("--database", default="sedar_dev")
    shell.set_defaults(handler=command_shell)
    serve = commands.add_parser("run", help="serve Odoo on a local port")
    serve.add_argument("--database", default="sedar_dev")
    serve.add_argument("--port", type=int, default=8069)
    serve.set_defaults(handler=command_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

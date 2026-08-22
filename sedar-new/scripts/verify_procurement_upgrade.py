#!/usr/bin/env python3
"""Verify the procurement release through an isolated legacy-to-candidate upgrade."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_BASE = "3b6aaa60e297886c521bb15c716d3d41fedb1001"
MODULES_RE = re.compile(r'SEDAR_MODULES="([a-z0-9_,]+)"')
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
SNAPSHOT_MARKER = "SEDAR_RELEASE_SNAPSHOT="
EXPECTED_PM_MODELS = {
    "pm_request": "sedar.purchase.request",
    "pm_request_line_a": "sedar.purchase.request.line",
    "pm_request_line_b": "sedar.purchase.request.line",
    "pm_request_line_c": "sedar.purchase.request.line",
    "pm_product_a_filter": "product.product",
    "pm_product_b_lube": "product.product",
    "pm_product_c_replacement_pump": "product.product",
    "pm_bidder_1": "res.partner",
    "pm_bidder_2": "res.partner",
    "pm_bidder_3": "res.partner",
    "pm_bid_1": "sedar.purchase.bid",
    "pm_bid_2": "sedar.purchase.bid",
    "pm_bid_3": "sedar.purchase.bid",
    "pm_bid_line_one_a": "sedar.purchase.bid.line",
    "pm_bid_line_one_b": "sedar.purchase.bid.line",
    "pm_bid_line_two_a": "sedar.purchase.bid.line",
    "pm_bid_line_three_b": "sedar.purchase.bid.line",
    "pm_bid_line_three_c": "sedar.purchase.bid.line",
    "pm_award_a": "sedar.purchase.line.award",
    "pm_award_b": "sedar.purchase.line.award",
    "pm_award_c": "sedar.purchase.line.award",
    "pm_purchase_order_bidder_one": "purchase.order",
    "pm_purchase_order_bidder_three": "purchase.order",
    "pm_purchase_order_line_a": "purchase.order.line",
    "pm_purchase_order_line_b": "purchase.order.line",
    "pm_purchase_order_line_c": "purchase.order.line",
    "pm_receipt_bidder_one": "stock.picking",
    "pm_receipt_bidder_three": "stock.picking",
    "pm_product_c_serial": "stock.lot",
    "pm_inventory_issue_a": "sedar.inventory.issue",
    "pm_inventory_issue_move_a": "stock.move",
    "pm_inventory_lifecycle_a": "sedar.inventory.lifecycle",
    "pm_running_hour_baseline": "sedar.equipment.running.hour.reading",
    "pm_running_hour_current": "sedar.equipment.running.hour.reading",
    "pm_due_maintenance_activity": "mail.activity",
    "pm_bid_one_quotation": "ir.attachment",
    "pm_bid_two_quotation": "ir.attachment",
    "pm_bid_three_quotation": "ir.attachment",
}


class VerificationError(RuntimeError):
    """Raised when a release-gate command or invariant fails."""


@dataclass
class VerificationRun:
    source_root: Path
    base_ref: str
    keep_success: bool
    run_root: Path
    workspace: Path
    project: str
    database: str = "sedar_release"
    fresh_database: str = "sedar_release_fresh"
    commands: list[dict] = field(default_factory=list)
    candidate_sha: str = ""
    candidate_tree_sha256: str = ""
    candidate_dirty: bool = False

    @property
    def compose_root(self) -> Path:
        return self.workspace / "sedar-new"

    @property
    def logs(self) -> Path:
        return self.run_root / "logs"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    return project_root().parent


def validate_ref(ref: str) -> str:
    if not SAFE_REF_RE.fullmatch(ref) or ".." in ref:
        raise VerificationError("Refusing unsafe Git base reference.")
    return ref


def compose_modules(compose_file: Path) -> list[str]:
    match = MODULES_RE.search(compose_file.read_text())
    if not match:
        raise VerificationError(f"Could not find SEDAR_MODULES in {compose_file}.")
    return match.group(1).split(",")


def command_output(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode:
        raise VerificationError(result.stderr.strip() or "Command failed: " + " ".join(command))
    return result.stdout.strip()


def candidate_tree_digest(source_root: Path) -> str:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=source_root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise VerificationError("Could not enumerate the candidate source tree.")
    digest = hashlib.sha256()
    for raw_path in sorted(filter(None, result.stdout.split(b"\0"))):
        path = source_root / raw_path.decode()
        if not path.is_file():
            continue
        digest.update(len(raw_path).to_bytes(8, "big"))
        digest.update(raw_path)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def run_logged(run: VerificationRun, name: str, command: list[str], cwd: Path, stdin: str | None = None) -> str:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(
        command,
        cwd=cwd,
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    log_path = run.logs / f"{len(run.commands) + 1:02d}-{name}.log"
    log_path.write_text(output)
    run.commands.append({
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "started_at": started,
        "exit_code": result.returncode,
        "log": str(log_path),
    })
    if result.returncode:
        raise VerificationError(f"{name} failed with exit {result.returncode}; see {log_path}.")
    return output


def create_run(source_root: Path, base_ref: str, keep_success: bool) -> VerificationRun:
    run_root = Path(tempfile.mkdtemp(prefix="sedar-procurement-release-"))
    workspace = run_root / "workspace"
    workspace.mkdir()
    (run_root / "logs").mkdir()
    token = secrets.token_hex(5)
    status = command_output(["git", "status", "--porcelain=v1"], source_root)
    return VerificationRun(
        source_root=source_root,
        base_ref=validate_ref(base_ref),
        keep_success=keep_success,
        run_root=run_root,
        workspace=workspace,
        project=f"sedar_release_{token}",
        candidate_sha=command_output(["git", "rev-parse", "HEAD"], source_root),
        candidate_tree_sha256=candidate_tree_digest(source_root),
        candidate_dirty=bool(status),
    )


def archive_base(run: VerificationRun) -> None:
    archive = run.run_root / "base.tar"
    run_logged(run, "archive-base", ["git", "archive", "--format=tar", "--output", str(archive), run.base_ref, "sedar-new"], run.source_root)
    run_logged(run, "extract-base", ["tar", "-xf", str(archive), "-C", str(run.workspace)], run.source_root)
    (run.compose_root / "data" / "postgres").mkdir(parents=True)
    (run.compose_root / "data" / "odoo").mkdir(parents=True)


def compose_command(run: VerificationRun, *arguments: str) -> list[str]:
    return ["docker", "compose", "--project-name", run.project, *arguments]


def install_modules(
    run: VerificationRun,
    name: str,
    modules: list[str],
    database: str | None = None,
) -> None:
    command = compose_command(
        run,
        "run", "--rm", "-T", "odoo", "odoo",
        "-c", "/etc/odoo/odoo.conf", "-d", database or run.database,
        "-i", ",".join(modules), "-u", ",".join(modules),
        "--without-demo=true", "--stop-after-init", "--no-http",
    )
    run_logged(run, name, command, run.compose_root)


def snapshot_script(xmlids_only: bool) -> str:
    mode = "xmlids" if xmlids_only else "legacy"
    return f'''import json
excluded = {{"create_date", "create_uid", "write_date", "write_uid", "__last_update"}}
excluded_prefixes = ("message_", "activity_", "website_message_")
def clean(record):
    values = {{}}
    for name, field in record._fields.items():
        if name == "res_id":
            values[name] = record[name]
            continue
        if name in excluded or name.startswith(excluded_prefixes) or not getattr(field, "store", False):
            continue
        if field.type in {{"binary", "html"}}:
            continue
        value = record[name]
        if field.type == "many2one":
            values[name] = value.id or False
        elif field.type in {{"one2many", "many2many"}}:
            values[name] = sorted(value.ids)
        elif field.type in {{"date", "datetime"}}:
            values[name] = str(value) if value else False
        elif field.type in {{"boolean", "integer", "float", "monetary", "char", "text", "selection"}}:
            values[name] = value
    return values
rows = []
if "{mode}" == "xmlids":
    data = env["ir.model.data"].search([("module", "=", "sedar_demo_suite"), ("name", "=like", "pm_%")], order="model,name")
    for item in data:
        record = env[item.model].browse(item.res_id).exists()
        if record:
            rows.append({{"key": item.complete_name, "model": item.model, "id": item.res_id, "values": clean(record)}})
    request = env.ref("sedar_demo_suite.pm_request")
    equipment = env.ref("sedar_marine_maintenance.atlas_main_engine")
    issue = env.ref("sedar_demo_suite.pm_inventory_issue_a")
    product_a = env.ref("sedar_demo_suite.pm_product_a_filter")
    product_b = env.ref("sedar_demo_suite.pm_product_b_lube")
    product_c = env.ref("sedar_demo_suite.pm_product_c_replacement_pump")
    serial = env.ref("sedar_demo_suite.pm_product_c_serial")
    receipt_one = env.ref("sedar_demo_suite.pm_receipt_bidder_one")
    receipt_three = env.ref("sedar_demo_suite.pm_receipt_bidder_three")
    storage = env.company.sedar_default_storage_location_id
    bid_ids = request.bid_ids.ids
    env.cr.execute(
        "SELECT id FROM ir_attachment WHERE res_model = %s AND res_id = ANY(%s) ORDER BY id",
        ("sedar.purchase.bid", bid_ids),
    )
    attachment_ids = [row[0] for row in env.cr.fetchall()]
    rows.append({{"key": "sedar_demo_suite.__pm_semantic__", "model": "_semantic", "id": 0, "values": {{
        "request_line_ids": sorted(request.line_ids.ids),
        "bid_ids": sorted(bid_ids),
        "bid_line_ids": sorted(request.bid_ids.line_ids.ids),
        "award_ids": sorted(request.award_ids.ids),
        "purchase_order_ids": sorted(request.purchase_order_ids.ids),
        "attachment_ids": sorted(attachment_ids),
        "lifecycle_ids": sorted(env["sedar.inventory.lifecycle"].search([("issue_id", "=", issue.id)]).ids),
        "due_activity_ids": sorted(equipment._sedar_open_due_activities().ids),
        "reading_ids": sorted(equipment.sedar_running_hour_reading_ids.ids),
        "product_names": [product_a.name, product_b.name, product_c.name],
        "receipt_lines": sorted((line.product_id.id, line.quantity, line.lot_id.id or False) for line in (receipt_one | receipt_three).move_line_ids),
        "storage_quantities": [
            env["stock.quant"]._get_available_quantity(product_a, storage, strict=True),
            env["stock.quant"]._get_available_quantity(product_b, storage, strict=True),
            env["stock.quant"]._get_available_quantity(product_c, storage, lot_id=serial, strict=True),
        ],
        "tug_product_a_quantity": env["stock.quant"]._get_available_quantity(product_a, issue.tug_location_id, strict=True),
    }}}})
else:
    for model in ("sedar.purchase.request", "purchase.order", "sedar.inventory.issue", "sedar.inventory.lifecycle", "sedar.inventory.lifecycle.event", "stock.picking", "stock.move", "stock.move.line", "stock.lot", "stock.quant", "account.move", "account.move.line", "ir.attachment", "ir.model.data"):
        if model in env:
            domain = [("res_model", "in", ("sedar.purchase.request", "sedar.purchase.bid", "purchase.order", "sedar.inventory.issue"))] if model == "ir.attachment" else []
            if model == "ir.model.data":
                domain = [("module", "in", ("sedar_purchase_request", "sedar_marine_inventory", "sedar_demo_suite"))]
            for record in env[model].search(domain):
                rows.append({{"key": model + ":" + str(record.id), "model": model, "id": record.id, "values": clean(record)}})
print("{SNAPSHOT_MARKER}" + json.dumps(rows, sort_keys=True, default=str))
'''


def take_snapshot(
    run: VerificationRun,
    name: str,
    xmlids_only: bool,
    database: str | None = None,
) -> list[dict]:
    command = compose_command(
        run, "run", "--rm", "-T", "odoo", "odoo", "shell",
        "-c", "/etc/odoo/odoo.conf", "-d", database or run.database, "--no-http",
    )
    output = run_logged(run, name, command, run.compose_root, snapshot_script(xmlids_only))
    marker_lines = [line for line in output.splitlines() if line.startswith(SNAPSHOT_MARKER)]
    if len(marker_lines) != 1:
        raise VerificationError(f"{name} did not return exactly one snapshot marker.")
    return json.loads(marker_lines[0].removeprefix(SNAPSHOT_MARKER))


def sync_candidate(run: VerificationRun) -> None:
    candidate = run.source_root / "sedar-new"
    addons = run.compose_root / "custom-addons"
    shutil.rmtree(addons)
    shutil.copytree(candidate / "custom-addons", addons)
    shutil.copy2(candidate / "docker-compose.yml", run.compose_root / "docker-compose.yml")
    shutil.copytree(candidate / "config", run.compose_root / "config", dirs_exist_ok=True)


def compare_legacy(before: list[dict], after: list[dict]) -> None:
    after_by_key = {row["key"]: row for row in after}
    failures = []
    for old in before:
        current = after_by_key.get(old["key"])
        if not current:
            failures.append(f"missing {old['key']}")
            continue
        changed = {key: (value, current["values"].get(key)) for key, value in old["values"].items() if current["values"].get(key) != value}
        if changed:
            failures.append(f"changed {old['key']}: {changed}")
    if failures:
        raise VerificationError("Legacy facts changed: " + "; ".join(failures[:10]))


def pm_rows(snapshot: list[dict]) -> dict[str, dict]:
    return {
        row["key"].removeprefix("sedar_demo_suite."): row
        for row in snapshot
        if row["model"] != "_semantic"
    }


def pm_semantic(snapshot: list[dict]) -> dict:
    rows = [row for row in snapshot if row["model"] == "_semantic"]
    if len(rows) != 1:
        raise VerificationError("PM snapshot must contain one semantic-count row.")
    return rows[0]["values"]


def require_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise VerificationError(f"{message}: expected {expected!r}, got {actual!r}.")


def assert_pm_inventory(rows: dict[str, dict]) -> None:
    product = rows["pm_product_a_filter"]["id"]
    issue = rows["pm_inventory_issue_a"]["values"]
    move = rows["pm_inventory_issue_move_a"]
    lifecycle = rows["pm_inventory_lifecycle_a"]["values"]
    require_equal(issue.get("product_id"), product, "PM Inventory Issue product")
    require_equal(issue.get("stock_move_id"), move["id"], "PM Inventory Issue move")
    require_equal(move["values"].get("state"), "done", "PM Inventory Issue move state")
    require_equal(move["values"].get("location_id"), issue.get("source_location_id"), "PM Inventory Issue source")
    require_equal(move["values"].get("location_dest_id"), issue.get("tug_location_id"), "PM Inventory Issue destination")
    require_equal(lifecycle.get("issue_id"), rows["pm_inventory_issue_a"]["id"], "PM lifecycle issue")
    require_equal(lifecycle.get("issue_move_id"), move["id"], "PM lifecycle opening move")
    require_equal(lifecycle.get("state"), "open", "PM Currently In Use state")
    if lifecycle.get("open_qty", 0) <= 0:
        raise VerificationError("PM Currently In Use quantity must remain positive.")


def assert_pm_orders(rows: dict[str, dict]) -> None:
    order_one = rows["pm_purchase_order_bidder_one"]
    order_three = rows["pm_purchase_order_bidder_three"]
    line_a = rows["pm_purchase_order_line_a"]
    line_b = rows["pm_purchase_order_line_b"]
    line_c = rows["pm_purchase_order_line_c"]
    require_equal(line_a["values"].get("order_id"), order_one["id"], "Product A order")
    require_equal(line_b["values"].get("order_id"), order_one["id"], "Product B order")
    require_equal(line_c["values"].get("order_id"), order_three["id"], "Product C order")
    require_equal(line_a["values"].get("product_id"), rows["pm_product_a_filter"]["id"], "Product A allocation")
    require_equal(line_b["values"].get("product_id"), rows["pm_product_b_lube"]["id"], "Product B allocation")
    require_equal(line_c["values"].get("product_id"), rows["pm_product_c_replacement_pump"]["id"], "Product C allocation")
    require_equal(order_one["values"].get("partner_id"), rows["pm_bidder_1"]["id"], "Bidder 1 order")
    require_equal(order_three["values"].get("partner_id"), rows["pm_bidder_3"]["id"], "Bidder 3 order")


def assert_pm_bids_and_awards(rows: dict[str, dict]) -> None:
    coverage = {
        "pm_bid_line_one_a": ("pm_bid_1", "pm_request_line_a"),
        "pm_bid_line_one_b": ("pm_bid_1", "pm_request_line_b"),
        "pm_bid_line_two_a": ("pm_bid_2", "pm_request_line_a"),
        "pm_bid_line_three_b": ("pm_bid_3", "pm_request_line_b"),
        "pm_bid_line_three_c": ("pm_bid_3", "pm_request_line_c"),
    }
    for line_name, (bid_name, request_line_name) in coverage.items():
        values = rows[line_name]["values"]
        require_equal(values.get("bid_id"), rows[bid_name]["id"], f"{line_name} Bid")
        require_equal(values.get("request_line_id"), rows[request_line_name]["id"], f"{line_name} requested product")
    winners = {
        "pm_award_a": "pm_bid_line_one_a",
        "pm_award_b": "pm_bid_line_one_b",
        "pm_award_c": "pm_bid_line_three_c",
    }
    for award_name, bid_line_name in winners.items():
        require_equal(
            rows[award_name]["values"].get("bid_line_id"),
            rows[bid_line_name]["id"],
            f"{award_name} winner",
        )


def assert_pm_readings(rows: dict[str, dict]) -> None:
    baseline = rows["pm_running_hour_baseline"]["values"]
    current = rows["pm_running_hour_current"]["values"]
    require_equal(current.get("equipment_id"), baseline.get("equipment_id"), "PM reading Equipment")
    if current.get("running_hours", -1) <= baseline.get("running_hours", -1):
        raise VerificationError("PM current Running Hours must exceed the baseline reading.")
    request = rows["pm_request"]["values"]
    require_equal(request.get("equipment_id"), current.get("equipment_id"), "PM request Equipment")
    require_equal(len(request.get("line_ids", [])), 3, "PM request line count")
    require_equal(
        rows["pm_due_maintenance_activity"]["values"].get("res_id"),
        current.get("equipment_id"),
        "PM due activity Equipment",
    )


def assert_pm_content(rows: dict[str, dict], semantic: dict) -> None:
    product_names = [
        "Product A — Main Engine Oil Filter Set",
        "Product B — Marine Engine Oil",
        "Product C — Replacement Cooling-Water Pump",
    ]
    require_equal(semantic["product_names"], product_names, "PM product names")
    product_specs = {
        "pm_product_a_filter": ("SEDAR-PM-A-FILTER", "ME-OF-500"),
        "pm_product_b_lube": ("SEDAR-PM-B-LUBE", "MEO-15W40"),
        "pm_product_c_replacement_pump": ("SEDAR-PM-C-PUMP", "CWP-500-R"),
    }
    for name, (code, part) in product_specs.items():
        require_equal(rows[name]["values"].get("default_code"), code, f"{name} code")
        require_equal(rows[name]["values"].get("sedar_manufacturer_part_number"), part, f"{name} part number")
    line_specs = {
        "pm_request_line_a": (4.0, 850.0),
        "pm_request_line_b": (60.0, 320.0),
        "pm_request_line_c": (1.0, 185000.0),
    }
    for name, (quantity, estimate) in line_specs.items():
        require_equal(rows[name]["values"].get("quantity"), quantity, f"{name} quantity")
        require_equal(rows[name]["values"].get("estimated_unit_price"), estimate, f"{name} estimate")
    bid_prices = {
        "pm_bid_line_one_a": 780.0,
        "pm_bid_line_one_b": 305.0,
        "pm_bid_line_two_a": 745.0,
        "pm_bid_line_three_b": 330.0,
        "pm_bid_line_three_c": 179500.0,
    }
    for name, price in bid_prices.items():
        require_equal(rows[name]["values"].get("unit_price"), price, f"{name} unit price")
    for name in ("pm_bid_1", "pm_bid_2", "pm_bid_3"):
        values = rows[name]["values"]
        require_equal(values.get("state"), "received", f"{name} state")
        require_equal(values.get("delivery_terms"), "Delivered to SEDAR Storage, Batangas.", f"{name} delivery terms")
        require_equal(values.get("payment_terms"), "Thirty days from accepted delivery.", f"{name} payment terms")
        require_equal(values.get("warranty_notes"), "Manufacturer warranty applies.", f"{name} warranty")
    award_reasons = {
        "pm_award_a": "Bidder 1 offers the best delivery and total service value.",
        "pm_award_b": "Bidder 1 consolidates Products A and B in one delivery.",
        "pm_award_c": "Bidder 3 provides the required pump warranty and support.",
    }
    for name, reason in award_reasons.items():
        require_equal(rows[name]["values"].get("state"), "ordered", f"{name} state")
        require_equal(rows[name]["values"].get("award_reason"), reason, f"{name} reason")


def assert_pm_stock_and_evidence(rows: dict[str, dict], semantic: dict) -> None:
    for name in ("pm_purchase_order_bidder_one", "pm_purchase_order_bidder_three"):
        require_equal(rows[name]["values"].get("state"), "purchase", f"{name} state")
    order_quantities = {
        "pm_purchase_order_line_a": 4.0,
        "pm_purchase_order_line_b": 60.0,
        "pm_purchase_order_line_c": 1.0,
    }
    for name, quantity in order_quantities.items():
        require_equal(rows[name]["values"].get("product_qty"), quantity, f"{name} quantity")
    expected_receipt_lines = sorted([
        [rows["pm_product_a_filter"]["id"], 4.0, False],
        [rows["pm_product_b_lube"]["id"], 60.0, False],
        [rows["pm_product_c_replacement_pump"]["id"], 1.0, rows["pm_product_c_serial"]["id"]],
    ])
    require_equal(semantic["receipt_lines"], expected_receipt_lines, "PM receipt lines")
    require_equal(semantic["storage_quantities"], [3.0, 60.0, 1.0], "PM Storage quantities")
    require_equal(semantic["tug_product_a_quantity"], 1.0, "PM Currently In Use stock")
    require_equal(rows["pm_product_c_serial"]["values"].get("name"), "DEMO-CWP-500-0001", "PM serial")
    checksums = {
        "pm_bid_one_quotation": "1f592b4251759dc1f3f111c9498449f4dc10817a",
        "pm_bid_two_quotation": "ec318322a21a3bfa9e36302f03cfa9bb881d259a",
        "pm_bid_three_quotation": "7c9ed9383bd912dbe6af1e00aeb56fac2e4cc0b6",
    }
    for name, checksum in checksums.items():
        require_equal(rows[name]["values"].get("checksum"), checksum, f"{name} content checksum")
        require_equal(rows[name]["values"].get("public"), False, f"{name} public access")


def assert_pm_scenario(snapshot: list[dict]) -> None:
    rows = pm_rows(snapshot)
    semantic = pm_semantic(snapshot)
    require_equal(set(rows), set(EXPECTED_PM_MODELS), "PM stable XMLID set")
    for name, model in EXPECTED_PM_MODELS.items():
        require_equal(rows[name]["model"], model, f"PM model for {name}")
    assert_pm_bids_and_awards(rows)
    assert_pm_orders(rows)
    assert_pm_inventory(rows)
    assert_pm_readings(rows)
    assert_pm_content(rows, semantic)
    assert_pm_stock_and_evidence(rows, semantic)
    require_equal(semantic["request_line_ids"], sorted(rows[name]["id"] for name in ("pm_request_line_a", "pm_request_line_b", "pm_request_line_c")), "PM request lines")
    require_equal(semantic["bid_ids"], sorted(rows[name]["id"] for name in ("pm_bid_1", "pm_bid_2", "pm_bid_3")), "PM Bids")
    require_equal(semantic["bid_line_ids"], sorted(rows[name]["id"] for name in EXPECTED_PM_MODELS if name.startswith("pm_bid_line_")), "PM Bid lines")
    require_equal(semantic["award_ids"], sorted(rows[name]["id"] for name in ("pm_award_a", "pm_award_b", "pm_award_c")), "PM Line Awards")
    require_equal(semantic["purchase_order_ids"], sorted(rows[name]["id"] for name in ("pm_purchase_order_bidder_one", "pm_purchase_order_bidder_three")), "PM Purchase Orders")
    require_equal(semantic["attachment_ids"], sorted(rows[name]["id"] for name in ("pm_bid_one_quotation", "pm_bid_two_quotation", "pm_bid_three_quotation")), "PM quotation attachments")
    require_equal(semantic["lifecycle_ids"], [rows["pm_inventory_lifecycle_a"]["id"]], "PM Inventory Lifecycles")
    require_equal(semantic["due_activity_ids"], [rows["pm_due_maintenance_activity"]["id"]], "PM due activities")
    require_equal(semantic["reading_ids"], sorted(rows[name]["id"] for name in ("pm_running_hour_baseline", "pm_running_hour_current")), "PM Running Hour Readings")
    for receipt in ("pm_receipt_bidder_one", "pm_receipt_bidder_three"):
        require_equal(rows[receipt]["values"].get("state"), "done", f"{receipt} state")
    if rows["pm_receipt_bidder_one"]["id"] not in rows["pm_purchase_order_bidder_one"]["values"].get("picking_ids", []):
        raise VerificationError("Bidder 1 receipt is not linked to its Purchase Order.")
    if rows["pm_receipt_bidder_three"]["id"] not in rows["pm_purchase_order_bidder_three"]["values"].get("picking_ids", []):
        raise VerificationError("Bidder 3 receipt is not linked to its Purchase Order.")


def image_metadata(run: VerificationRun) -> dict:
    image_id = command_output(["docker", "image", "inspect", "--format", "{{.Id}}", "odoo:19.0"], run.source_root)
    repo_digests = command_output(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", "odoo:19.0"], run.source_root)
    return {"image": "odoo:19.0", "id": image_id, "repo_digests": json.loads(repo_digests or "[]")}


def verify(run: VerificationRun) -> dict:
    command_output(["git", "rev-parse", "--verify", f"{run.base_ref}^{{commit}}"], run.source_root)
    archive_base(run)
    base_modules = compose_modules(run.compose_root / "docker-compose.yml")
    run_logged(run, "compose-config-base", compose_command(run, "config", "--quiet"), run.compose_root)
    run_logged(run, "start-isolated-db", compose_command(run, "up", "-d", "--wait", "db"), run.compose_root)
    install_modules(run, "install-legacy-base", base_modules)
    legacy_before = take_snapshot(run, "snapshot-legacy-before", xmlids_only=False)
    sync_candidate(run)
    candidate_modules = compose_modules(run.compose_root / "docker-compose.yml")
    run_logged(run, "compose-config-candidate", compose_command(run, "config", "--quiet"), run.compose_root)
    install_modules(run, "install-candidate-fresh", candidate_modules, run.fresh_database)
    fresh_first = take_snapshot(
        run, "snapshot-pm-fresh-first", True, run.fresh_database
    )
    assert_pm_scenario(fresh_first)
    install_modules(run, "upgrade-candidate-fresh", candidate_modules, run.fresh_database)
    fresh_second = take_snapshot(
        run, "snapshot-pm-fresh-second", True, run.fresh_database
    )
    assert_pm_scenario(fresh_second)
    if fresh_first != fresh_second:
        raise VerificationError("Fresh PM fixture identity or semantic content changed on upgrade.")
    install_modules(run, "upgrade-candidate-first", candidate_modules)
    legacy_after = take_snapshot(run, "snapshot-legacy-after", xmlids_only=False)
    compare_legacy(legacy_before, legacy_after)
    first = take_snapshot(run, "snapshot-pm-first", xmlids_only=True)
    assert_pm_scenario(first)
    install_modules(run, "upgrade-candidate-second", candidate_modules)
    second = take_snapshot(run, "snapshot-pm-second", xmlids_only=True)
    assert_pm_scenario(second)
    if first != second:
        raise VerificationError("PM fixture identity or semantic content changed on the second upgrade.")
    legacy_second = take_snapshot(run, "snapshot-legacy-second", xmlids_only=False)
    compare_legacy(legacy_before, legacy_second)
    return {
        "status": "passed",
        "candidate_sha": run.candidate_sha,
        "candidate_tree_sha256": run.candidate_tree_sha256,
        "candidate_dirty": run.candidate_dirty,
        "base_ref": run.base_ref,
        "odoo_image": image_metadata(run),
        "database": run.database,
        "fresh_database": run.fresh_database,
        "compose_project": run.project,
        "isolated_data_path": str(run.compose_root / "data"),
        "base_modules": base_modules,
        "candidate_modules": candidate_modules,
        "legacy_record_count": len(legacy_before),
        "pm_fixture_count": len(first),
        "fresh_pm_fixture_count": len(fresh_first),
        "commands": run.commands,
    }


def write_report(run: VerificationRun, result: dict) -> Path:
    report = run.run_root / "report.json"
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return report


def cleanup(run: VerificationRun) -> None:
    root = run.run_root.resolve()
    compose_root = run.compose_root.resolve()
    data_root = (run.compose_root / "data").resolve()
    if root not in compose_root.parents or compose_root not in data_root.parents:
        raise VerificationError("Refusing cleanup outside the isolated verifier workspace.")
    result = subprocess.run(
        compose_command(run, "down", "--remove-orphans"),
        cwd=run.compose_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise VerificationError("Could not stop the isolated Compose project; evidence retained.")
    shutil.rmtree(run.run_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default=DEFAULT_BASE)
    parser.add_argument("--keep-success", action="store_true", help="Retain the successful isolated workspace and logs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    run = create_run(repo_root(), args.base_ref, args.keep_success)
    try:
        result = verify(run)
    except (VerificationError, OSError, json.JSONDecodeError) as error:
        result = {"status": "failed", "error": str(error), "candidate_sha": run.candidate_sha, "candidate_tree_sha256": run.candidate_tree_sha256, "candidate_dirty": run.candidate_dirty, "base_ref": run.base_ref, "database": run.database, "fresh_database": run.fresh_database, "compose_project": run.project, "isolated_workspace": str(run.run_root), "isolated_data_path": str(run.compose_root / "data"), "commands": run.commands}
        report = write_report(run, result)
        print(f"FAILED: evidence preserved at {run.run_root}; report: {report}", file=sys.stderr)
        return 1
    report = write_report(run, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if run.keep_success:
        print(f"Successful evidence retained at {run.run_root}; report: {report}")
    else:
        try:
            cleanup(run)
        except VerificationError as error:
            result.update({"status": "failed", "error": str(error), "isolated_workspace": str(run.run_root)})
            write_report(run, result)
            print(f"FAILED: {error} Evidence retained at {run.run_root}.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Drive the running SEDAR application in a headless browser and check the main workspaces open.

Needs a server on SEDAR_BASE_URL with the demo database. Pass --start to launch the native
server from scripts/native_odoo.py and stop it afterwards. Screenshots land in .local/smoke/.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / ".local" / "smoke"
BASE_URL = os.environ.get("SEDAR_BASE_URL", "http://localhost:8069")
DATABASE = os.environ.get("SEDAR_DB", "sedar_dev")
CHROMIUM = os.environ.get("SEDAR_CHROMIUM") or next(iter(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")), None)
ROW_SELECTOR = ".o_data_row, .o_kanban_record"


@dataclass
class Persona:
    login: str
    password: str


BILLING = Persona("billing@sedar.demo", "billingdemo")
CLIENT = Persona("client@sedar.demo", "clientdemo")


def wait_for_server(timeout: int = 240) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE_URL}/web/login", timeout=3)
            return
        except OSError:
            time.sleep(2)
    sys.exit(f"server did not answer at {BASE_URL}")


def log_in(page: Page, persona: Persona) -> None:
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/web/login?db={DATABASE}")
    page.fill("input[name=login]", persona.login)
    page.fill("input[name=password]", persona.password)
    page.click("form.oe_login_form button[type=submit]")
    page.wait_for_url(lambda url: "/web/login" not in url)


def open_action(page: Page, xmlid: str, name: str) -> int:
    page.goto(f"{BASE_URL}/odoo/action-{xmlid}")
    page.wait_for_selector(ROW_SELECTOR, timeout=30000)
    page.screenshot(path=str(SHOTS / f"{name}.png"))
    return page.locator(ROW_SELECTOR).count()


def check_service_order_dashboard(page: Page) -> str:
    rows = open_action(page, "sedar_marine_operations.action_service_order_dashboard", "service-orders")
    assert rows >= 5, f"expected seeded Service Orders, found {rows}"
    return f"{rows} Service Orders listed"


def check_marine_operations(page: Page) -> str:
    rows = open_action(page, "sedar_marine_dispatch.action_marine_operations", "marine-operations")
    assert rows >= 1, "expected at least one Marine Operation"
    return f"{rows} Marine Operations listed"


def check_billing_reviews(page: Page) -> str:
    rows = open_action(page, "sedar_marine_finance.action_billing_reviews", "billing-reviews")
    assert rows >= 1, "expected at least one Service Order in Billing Review"
    return f"{rows} Billing Reviews listed"


def check_client_portal_orders(page: Page) -> str:
    page.goto(f"{BASE_URL}/my/sedar/orders")
    page.wait_for_load_state("load")
    page.screenshot(path=str(SHOTS / "portal-orders.png"))
    assert "Service Order" in page.content(), "portal order list did not render"
    return "client portal order list rendered"


def check_client_portal_new_order_form(page: Page) -> str:
    page.goto(f"{BASE_URL}/my/sedar/orders/new")
    page.wait_for_load_state("load")
    page.screenshot(path=str(SHOTS / "portal-new-order.png"))
    assert page.locator("form").count() >= 1, "new Service Order form missing"
    return "new Service Order form rendered"


STEPS = [
    (BILLING, "service order dashboard", check_service_order_dashboard),
    (BILLING, "marine operations", check_marine_operations),
    (BILLING, "billing reviews", check_billing_reviews),
    (CLIENT, "client portal orders", check_client_portal_orders),
    (CLIENT, "client portal new order", check_client_portal_new_order_form),
]


def run_steps() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    failures = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROMIUM) if CHROMIUM else None)
        page = browser.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        current: Persona | None = None
        for persona, name, step in STEPS:
            if persona is not current:
                log_in(page, persona)
                current = persona
            try:
                detail = step(page)
                print(f"ok   {name}: {detail}")
            except Exception as error:
                failures += 1
                print(f"FAIL {name}: {str(error).splitlines()[0]}")
        browser.close()
    for error in page_errors:
        failures += 1
        print(f"FAIL browser error: {error[:200]}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="start and stop a native server around the run")
    args = parser.parse_args()
    server = None
    if args.start:
        server = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "native_odoo.py"), "run", "--database", DATABASE],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
    try:
        wait_for_server()
        failures = run_steps()
    finally:
        if server:
            server.terminate()
            server.wait(timeout=30)
    print(f"smoke: {failures} failure(s), screenshots in {SHOTS}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

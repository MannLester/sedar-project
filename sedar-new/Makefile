PYTHON ?= python3
TOOLS := $(if $(wildcard .venv/bin/ruff),.venv/bin/,)
TOOLS_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))
MODULES := $(foreach module,$(M),--module $(module))
DOCKER_AVAILABLE := $(shell docker info >/dev/null 2>&1 && echo yes)

.PHONY: help tools check lint arch unit baseline test install shell run smoke native-setup up down

help:
	@echo "check        static checks (ruff, pylint-odoo, architecture, script tests)"
	@echo "test M=...   run Odoo tests for addons M (Docker when available, else native)"
	@echo "install      install every SEDAR module into a fresh database (native)"
	@echo "shell        Odoo shell on the seeded database (native)"
	@echo "run          serve Odoo natively on http://localhost:8069"
	@echo "smoke        browser walkthrough against a running server"
	@echo "baseline     rewrite architecture/baseline.json after fixing legacy violations"
	@echo "native-setup install PostgreSQL, Odoo 19 source and virtualenv without Docker"
	@echo "tools        create .venv with the linters"
	@echo "up / down    Docker Compose stack"

tools:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q -r requirements-dev.txt

check: lint arch unit

lint:
	$(TOOLS)ruff check custom-addons scripts
	$(TOOLS_PYTHON) -m pylint --rcfile=.pylintrc custom-addons

arch:
	$(PYTHON) scripts/check.py

unit:
	PYTHONPATH=scripts $(PYTHON) -m unittest discover -s scripts/tests -p 'test_*.py'

baseline:
	$(PYTHON) scripts/check.py --update-baseline

test:
	@test -n "$(M)" || { echo "usage: make test M=<addon> [M=<addon> ...]"; exit 2; }
ifeq ($(DOCKER_AVAILABLE),yes)
	$(PYTHON) scripts/run_odoo_tests.py $(MODULES)
else
	$(PYTHON) scripts/native_odoo.py test $(MODULES)
endif

native-setup:
	$(PYTHON) scripts/native_odoo.py setup

install:
	$(PYTHON) scripts/native_odoo.py install --database sedar_dev --replace

shell:
	$(PYTHON) scripts/native_odoo.py shell --database sedar_dev

run:
	$(PYTHON) scripts/native_odoo.py run --database sedar_dev

smoke:
	$(TOOLS_PYTHON) scripts/smoke.py --start

up:
	docker compose up -d

down:
	docker compose down

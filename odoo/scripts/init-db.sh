#!/usr/bin/env sh
set -eu

docker compose exec -T odoo odoo -d sedar_mvp -i sedar_marine_mvp --stop-after-init --no-http
docker compose restart odoo


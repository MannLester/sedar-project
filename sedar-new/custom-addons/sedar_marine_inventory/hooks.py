MODULE = "sedar_marine_inventory"


def _record(env, model, xmlid, values):
    data = env["ir.model.data"].search([
        ("module", "=", MODULE), ("name", "=", xmlid)
    ], limit=1)
    if data:
        record = env[model].browse(data.res_id).exists()
        if record:
            record.write(values)
            return record
        data.unlink()
    record = env[model].create(values)
    env["ir.model.data"].create({
        "module": MODULE,
        "name": xmlid,
        "model": model,
        "res_id": record.id,
        "noupdate": True,
    })
    return record


def _available(env, product, location):
    return env["stock.quant"]._get_available_quantity(product, location, strict=False)


def _set_available(env, product, location, quantity):
    current = _available(env, product, location)
    delta = quantity - current
    if abs(delta) > 1e-6:
        env["stock.quant"]._update_available_quantity(product, location, delta)


def post_init_hook(env):
    company = env.company
    warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
    if not warehouse:
        warehouse = env["stock.warehouse"].create({
            "name": "SEDAR Demo Warehouse",
            "code": "SDR",
            "company_id": company.id,
            "partner_id": company.partner_id.id,
        })
    stock_location = warehouse.lot_stock_id

    tug_parent_location = _record(env, "stock.location", "location_tugboats", {
        "name": "SEDAR Tugboats",
        "usage": "internal",
        "location_id": stock_location.id,
        "company_id": company.id,
    })

    unit = env.ref("uom.product_uom_unit")
    liter = env.ref("uom.product_uom_litre", raise_if_not_found=False) or unit
    products = {
        "diesel": _record(env, "product.product", "product_marine_diesel", {
            "name": "Demo Marine Diesel",
            "type": "consu",
            "is_storable": True,
            "uom_id": liter.id,
            "default_code": "SEDAR-FUEL-DIESEL",
            "barcode": "SEDAR000001",
        }),
        "lube": _record(env, "product.product", "product_engine_lube", {
            "name": "Demo Engine Lube Oil",
            "type": "consu",
            "is_storable": True,
            "uom_id": liter.id,
            "default_code": "SEDAR-LUBE-ENGINE",
            "barcode": "SEDAR000002",
        }),
        "filter": _record(env, "product.product", "product_fuel_filter", {
            "name": "Demo Fuel Filter Element",
            "type": "consu",
            "is_storable": True,
            "uom_id": unit.id,
            "default_code": "SEDAR-SP-FILTER",
            "barcode": "SEDAR000003",
        }),
        "packing": _record(env, "product.product", "product_pump_packing", {
            "name": "Demo Pump Packing Kit",
            "type": "consu",
            "is_storable": True,
            "uom_id": unit.id,
            "default_code": "SEDAR-SP-PACKING",
            "barcode": "SEDAR000004",
        }),
    }

    _set_available(env, products["diesel"], stock_location, 180000)
    _set_available(env, products["lube"], stock_location, 1200)
    _set_available(env, products["filter"], stock_location, 24)
    _set_available(env, products["packing"], stock_location, 2)

    services = {
        key: env.ref(f"sedar_marine_operations.service_type_{key}")
        for key in ["harbor", "berthing", "towage", "shifting", "emergency"]
    }
    template_specs = {
        "harbor": [(products["diesel"], 450), (products["lube"], 5)],
        "berthing": [(products["diesel"], 550), (products["lube"], 6)],
        "towage": [(products["diesel"], 1200), (products["lube"], 12)],
        "shifting": [(products["diesel"], 700), (products["lube"], 8)],
        "emergency": [(products["diesel"], 1500), (products["lube"], 15)],
    }
    for service_key, lines in template_specs.items():
        template = _record(env, "sedar.inventory.template", f"template_{service_key}", {
            "name": f"Demo {services[service_key].name} Inventory",
            "service_type_id": services[service_key].id,
            "source_location_id": stock_location.id,
            "active": True,
        })
        for index, (product, quantity) in enumerate(lines, start=1):
            _record(env, "sedar.inventory.template.line", f"template_{service_key}_{product.default_code.lower().replace('-', '_')}", {
                "template_id": template.id,
                "sequence": index * 10,
                "product_id": product.id,
                "required_qty": quantity,
                "per_tug": True,
            })

    for xmlid in [
        "sedar_service_order_demo.tug_atlas",
        "sedar_service_order_demo.tug_harbor_one",
        "sedar_service_order_demo.tug_matikas",
        "sedar_service_order_demo.tug_bantay",
        "sedar_service_order_demo.tug_lakas",
    ]:
        tug = env.ref(xmlid, raise_if_not_found=False)
        if not tug:
            continue
        location = _record(env, "stock.location", f"location_{tug.registration_number.lower().replace('-', '_')}", {
            "name": tug.name,
            "usage": "internal",
            "location_id": tug_parent_location.id,
            "company_id": company.id,
        })
        tug.write({"stock_location_id": location.id})
        _set_available(env, products["diesel"], location, 12000)
        _set_available(env, products["lube"], location, 80)

    orders = env["sedar.marine.service.order"].search([
        ("state", "in", ["planning", "blocked", "ready", "dispatched", "in_progress", "completed"]),
    ])
    for order in orders:
        order.action_generate_inventory_requirements()
        order._sync_inventory_readiness()
    orders._sync_automated_readiness()

    work_order = env["maintenance.request"].search([
        ("sedar_tugboat_id", "!=", False),
        ("close_date", "=", False),
    ], limit=1)
    if work_order:
        _record(env, "sedar.maintenance.part.line", "line_demo_filter_shortage", {
            "maintenance_request_id": work_order.id,
            "product_id": products["filter"].id,
            "source_location_id": stock_location.id,
            "requested_qty": 4,
            "reserved_qty": 0,
            "issued_qty": 0,
            "consumed_qty": 0,
        })

    completed_operation = env.ref("sedar_marine_dispatch_demo.operation_completed", raise_if_not_found=False)
    if completed_operation and completed_operation.tug_operation_ids:
        tug = completed_operation.tug_operation_ids[:1].tugboat_id
        _record(env, "sedar.operation.fuel.log", "fuel_completed_operation", {
            "operation_id": completed_operation.id,
            "tugboat_id": tug.id,
            "product_id": products["diesel"].id,
            "source_location_id": stock_location.id,
            "tug_location_id": tug.stock_location_id.id,
            "opening_qty": 12000,
            "issued_qty": 850,
            "consumed_qty": 620,
            "state": "consumed",
            "note": "Demo completed-operation fuel consumption.",
        })

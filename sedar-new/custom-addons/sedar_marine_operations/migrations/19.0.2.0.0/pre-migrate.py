from odoo.exceptions import UserError


ORDER_TABLE = "sedar_marine_service_order"


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _candidate_queries(cr):
    queries = [
        "SELECT id AS order_id, company_id FROM sedar_marine_service_order WHERE company_id IS NOT NULL",
        """
        SELECT orders.id, partner.company_id
          FROM sedar_marine_service_order orders
          JOIN res_partner partner ON partner.id = orders.client_id
         WHERE partner.company_id IS NOT NULL
        """,
        """
        SELECT orders.id, partner.company_id
          FROM sedar_marine_service_order orders
          JOIN res_partner partner ON partner.id = orders.contact_id
         WHERE partner.company_id IS NOT NULL
        """,
    ]
    optional_sources = [
        (
            "account_move", "sedar_service_order_id", "company_id",
            "SELECT sedar_service_order_id, company_id FROM account_move "
            "WHERE sedar_service_order_id IS NOT NULL AND company_id IS NOT NULL",
        ),
        (
            "sedar_purchase_request", "service_order_id", "company_id",
            "SELECT service_order_id, company_id FROM sedar_purchase_request "
            "WHERE service_order_id IS NOT NULL AND company_id IS NOT NULL",
        ),
    ]
    for table, order_column, company_column, query in optional_sources:
        if (
            _table_exists(cr, table)
            and _column_exists(cr, table, order_column)
            and _column_exists(cr, table, company_column)
        ):
            queries.append(query)
    if (
        _table_exists(cr, "sedar_inventory_requirement")
        and _column_exists(cr, "sedar_inventory_requirement", "order_id")
        and _column_exists(cr, "sedar_inventory_requirement", "source_location_id")
    ):
        queries.append(
            """
            SELECT requirement.order_id, location.company_id
              FROM sedar_inventory_requirement requirement
              JOIN stock_location location ON location.id = requirement.source_location_id
             WHERE location.company_id IS NOT NULL
            """
        )
    return queries


def _main_company_id(cr):
    cr.execute(
        """
        SELECT company.id
          FROM ir_model_data data
          JOIN res_company company ON company.id = data.res_id
         WHERE data.module = 'base'
           AND data.name = 'main_company'
           AND data.model = 'res.company'
         LIMIT 1
        """
    )
    row = cr.fetchone()
    if row:
        return row[0]
    cr.execute("SELECT id FROM res_company ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if not row:
        raise UserError("Service Order migration requires at least one company.")
    return row[0]


def _invalid_nested_dispatch_links(cr):
    checks = [
        (
            "Operation Tug",
            ("sedar_marine_operation_tug", "sedar_marine_operation", "sedar_tug_assignment"),
            """
            SELECT operation_tug.id
              FROM sedar_marine_operation_tug operation_tug
              JOIN sedar_marine_operation operation
                ON operation.id = operation_tug.operation_id
              JOIN sedar_tug_assignment assignment
                ON assignment.id = operation_tug.tug_assignment_id
             WHERE operation.order_id != assignment.order_id
             ORDER BY operation_tug.id
            """,
        ),
        (
            "Operation Crew",
            ("sedar_marine_operation_crew", "sedar_marine_operation_tug", "sedar_crew_assignment"),
            """
            SELECT operation_crew.id
              FROM sedar_marine_operation_crew operation_crew
              JOIN sedar_marine_operation_tug operation_tug
                ON operation_tug.id = operation_crew.operation_tug_id
              JOIN sedar_crew_assignment crew_assignment
                ON crew_assignment.id = operation_crew.crew_assignment_id
             WHERE crew_assignment.tug_assignment_id != operation_tug.tug_assignment_id
             ORDER BY operation_crew.id
            """,
        ),
        (
            "Operation Log",
            ("sedar_marine_operation_log", "sedar_marine_operation_tug"),
            """
            SELECT operation_log.id
              FROM sedar_marine_operation_log operation_log
              JOIN sedar_marine_operation_tug operation_tug
                ON operation_tug.id = operation_log.operation_tug_id
             WHERE operation_log.operation_id != operation_tug.operation_id
             ORDER BY operation_log.id
            """,
        ),
        (
            "Operation Delay",
            ("sedar_marine_operation_delay", "sedar_marine_operation_tug"),
            """
            SELECT operation_delay.id
              FROM sedar_marine_operation_delay operation_delay
              JOIN sedar_marine_operation_tug operation_tug
                ON operation_tug.id = operation_delay.operation_tug_id
             WHERE operation_delay.operation_id != operation_tug.operation_id
             ORDER BY operation_delay.id
            """,
        ),
    ]
    invalid = []
    for label, tables, query in checks:
        if all(_table_exists(cr, table) for table in tables):
            cr.execute(query)
            record_ids = [row[0] for row in cr.fetchall()]
            if record_ids:
                invalid.append(f"{label} IDs {record_ids}")
    return invalid


def _validate_nested_dispatch_links(cr):
    invalid = _invalid_nested_dispatch_links(cr)
    if invalid:
        raise UserError(
            "Cannot migrate Service Order companies because legacy dispatch links conflict: "
            + "; ".join(invalid)
        )


def _assign_companies(cr):
    union = " UNION ALL ".join(_candidate_queries(cr))
    cr.execute(
        f"""
        SELECT order_id, array_agg(DISTINCT company_id ORDER BY company_id)
          FROM ({union}) candidates
         GROUP BY order_id
        HAVING count(DISTINCT company_id) > 1
        """
    )
    conflicts = cr.fetchall()
    if conflicts:
        details = ", ".join(
            f"Service Order {order_id}: companies {company_ids}"
            for order_id, company_ids in conflicts
        )
        raise UserError(
            "Cannot assign Service Order companies because company-owned evidence conflicts: "
            + details
        )
    cr.execute(
        f"""
        WITH resolved AS (
            SELECT order_id, min(company_id) AS company_id
              FROM ({union}) candidates
             GROUP BY order_id
        )
        UPDATE {ORDER_TABLE} orders
           SET company_id = resolved.company_id
          FROM resolved
         WHERE orders.id = resolved.order_id
           AND orders.company_id IS DISTINCT FROM resolved.company_id
        """
    )
    cr.execute(
        f"UPDATE {ORDER_TABLE} SET company_id = %s WHERE company_id IS NULL",
        (_main_company_id(cr),),
    )


def migrate(cr, version):
    if not _table_exists(cr, ORDER_TABLE):
        return
    cr.execute(f"ALTER TABLE {ORDER_TABLE} ADD COLUMN IF NOT EXISTS company_id integer")
    _validate_nested_dispatch_links(cr)
    _assign_companies(cr)
    cr.execute(f"ALTER TABLE {ORDER_TABLE} ALTER COLUMN company_id SET NOT NULL")

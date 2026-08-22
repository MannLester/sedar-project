from odoo.exceptions import UserError


TUGBOAT_TABLE = "sedar_tugboat"


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


def _has_columns(cr, table, *columns):
    return _table_exists(cr, table) and all(
        _column_exists(cr, table, column) for column in columns
    )


def _candidate_queries(cr):
    queries = [
        "SELECT id AS tugboat_id, company_id "
        "FROM sedar_tugboat WHERE company_id IS NOT NULL"
    ]
    if _has_columns(cr, "sedar_tug_assignment", "tugboat_id", "order_id"):
        queries.append(
            """
            SELECT assignment.tugboat_id, service_order.company_id
              FROM sedar_tug_assignment assignment
              JOIN sedar_marine_service_order service_order
                ON service_order.id = assignment.order_id
             WHERE service_order.company_id IS NOT NULL
            """
        )
    if (
        _has_columns(cr, TUGBOAT_TABLE, "stock_location_id")
        and _has_columns(cr, "stock_location", "company_id")
    ):
        queries.append(
            """
            SELECT tugboat.id, location.company_id
              FROM sedar_tugboat tugboat
              JOIN stock_location location ON location.id = tugboat.stock_location_id
             WHERE location.company_id IS NOT NULL
            """
        )
    if (
        _has_columns(cr, "sedar_inventory_issue", "tugboat_id", "source_location_id")
        and _has_columns(cr, "stock_location", "company_id")
    ):
        queries.append(
            """
            SELECT issue.tugboat_id, location.company_id
              FROM sedar_inventory_issue issue
              JOIN stock_location location ON location.id = issue.source_location_id
             WHERE location.company_id IS NOT NULL
            """
        )
    if _has_columns(cr, "maintenance_equipment", "sedar_tugboat_id", "company_id"):
        queries.append(
            """
            SELECT sedar_tugboat_id, company_id
              FROM maintenance_equipment
             WHERE sedar_tugboat_id IS NOT NULL
               AND company_id IS NOT NULL
            """
        )
    return queries


def _assign_companies(cr):
    union = " UNION ALL ".join(_candidate_queries(cr))
    cr.execute(
        f"""
        SELECT tugboat_id, array_agg(DISTINCT company_id ORDER BY company_id)
          FROM ({union}) candidates
         GROUP BY tugboat_id
        HAVING count(DISTINCT company_id) > 1
        """
    )
    conflicts = cr.fetchall()
    if conflicts:
        details = ", ".join(
            f"Tugboat {tugboat_id}: companies {company_ids}"
            for tugboat_id, company_ids in conflicts
        )
        raise UserError("Tugboat company evidence conflicts: " + details)

    cr.execute(
        f"""
        WITH resolved AS (
            SELECT tugboat_id, min(company_id) AS company_id
              FROM ({union}) candidates
             GROUP BY tugboat_id
        )
        UPDATE {TUGBOAT_TABLE} tugboat
           SET company_id = resolved.company_id
          FROM resolved
         WHERE tugboat.id = resolved.tugboat_id
           AND tugboat.company_id IS DISTINCT FROM resolved.company_id
        """
    )
    cr.execute(
        f"SELECT id FROM {TUGBOAT_TABLE} WHERE company_id IS NULL ORDER BY id"
    )
    missing_ids = [row[0] for row in cr.fetchall()]
    if missing_ids:
        raise UserError(
            "Tugboat company evidence is missing; affected Tugboat IDs: "
            f"{missing_ids}."
        )


def migrate(cr, version):
    if not _table_exists(cr, TUGBOAT_TABLE):
        return
    cr.execute(
        f"ALTER TABLE {TUGBOAT_TABLE} ADD COLUMN IF NOT EXISTS company_id integer"
    )
    _assign_companies(cr)
    cr.execute(
        f"CREATE INDEX IF NOT EXISTS {TUGBOAT_TABLE}_company_id_index "
        f"ON {TUGBOAT_TABLE} (company_id)"
    )
    cr.execute(f"ALTER TABLE {TUGBOAT_TABLE} ALTER COLUMN company_id SET NOT NULL")

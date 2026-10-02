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


def migrate(cr, version):
    """Preserve legacy order-level demand before adding tug-specific readiness."""
    if not _column_exists(cr, "sedar_inventory_requirement", "tug_assignment_id"):
        cr.execute(
            "ALTER TABLE sedar_inventory_requirement ADD COLUMN tug_assignment_id integer"
        )
    if not _column_exists(cr, "sedar_inventory_requirement", "expected_consumption_qty"):
        cr.execute(
            """
            ALTER TABLE sedar_inventory_requirement
            ADD COLUMN expected_consumption_qty double precision NOT NULL DEFAULT 1.0
            """
        )
        cr.execute(
            """
            UPDATE sedar_inventory_requirement
               SET expected_consumption_qty = required_qty
             WHERE required_qty IS NOT NULL
            """
        )
    if not _column_exists(cr, "sedar_inventory_requirement", "minimum_reserve_qty"):
        cr.execute(
            """
            ALTER TABLE sedar_inventory_requirement
            ADD COLUMN minimum_reserve_qty double precision NOT NULL DEFAULT 0.0
            """
        )

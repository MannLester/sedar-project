def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


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


def _reject_relief_assignment_conflicts(cr):
    required_columns = {
        "sedar_crew_shortage": {"company_id"},
        "sedar_crew_shortage_action": {"shortage_id", "relief_assignment_id"},
        "sedar_crew_assignment": {"company_id"},
    }
    if not all(
        _table_exists(cr, table)
        and all(_column_exists(cr, table, column) for column in columns)
        for table, columns in required_columns.items()
    ):
        return

    cr.execute(
        """
        SELECT action.id
          FROM sedar_crew_shortage_action action
          JOIN sedar_crew_shortage shortage
            ON shortage.id = action.shortage_id
          JOIN sedar_crew_assignment assignment
            ON assignment.id = action.relief_assignment_id
         WHERE assignment.company_id IS DISTINCT FROM shortage.company_id
         ORDER BY action.id
        """
    )
    action_ids = [row[0] for row in cr.fetchall()]
    if action_ids:
        raise RuntimeError(
            "Crew shortage relief assignments conflict with their shortage company; "
            f"action IDs: {action_ids}."
        )


def migrate(cr, version):
    """Refuse relief assignments that cross the shortage company boundary."""
    _reject_relief_assignment_conflicts(cr)

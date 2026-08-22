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


def _reject_legacy_link_conflicts(cr):
    checks = [
        (
            "Crew Shortage crew assignments conflict with their Service Order company",
            """
            SELECT shortage.id
              FROM sedar_crew_shortage shortage
              JOIN sedar_crew_assignment assignment
                ON assignment.id = shortage.crew_assignment_id
             WHERE assignment.company_id IS DISTINCT FROM shortage.company_id
             ORDER BY shortage.id
            """,
        ),
        (
            "Crew Shortage Marine Operations conflict with their Service Order company",
            """
            SELECT shortage.id
              FROM sedar_crew_shortage shortage
              JOIN sedar_marine_operation operation
                ON operation.id = shortage.operation_id
             WHERE operation.company_id IS DISTINCT FROM shortage.company_id
             ORDER BY shortage.id
            """,
        ),
        (
            "Crew Shortage manpower lines conflict with their Service Order company",
            """
            SELECT shortage.id
              FROM sedar_crew_shortage shortage
              JOIN sedar_manpower_request_line line
                ON line.id = shortage.manpower_request_line_id
              JOIN sedar_manpower_request request
                ON request.id = line.request_id
             WHERE request.company_id IS DISTINCT FROM shortage.company_id
             ORDER BY shortage.id
            """,
        ),
        (
            "Crew Shortage actions have employees from another company",
            """
            SELECT action.id
              FROM sedar_crew_shortage_action action
              JOIN sedar_crew_shortage shortage
                ON shortage.id = action.shortage_id
              JOIN hr_employee employee
                ON employee.id = action.assigned_employee_id
             WHERE employee.company_id IS NOT NULL
               AND employee.company_id != shortage.company_id
             ORDER BY action.id
            """,
        ),
        (
            "Manpower Request lines have HR jobs from another company",
            """
            SELECT line.id
              FROM sedar_manpower_request_line line
              JOIN sedar_manpower_request request
                ON request.id = line.request_id
              JOIN hr_job job
                ON job.id = line.job_id
             WHERE job.company_id IS NOT NULL
               AND job.company_id != request.company_id
             ORDER BY line.id
            """,
        ),
    ]
    for label, query in checks:
        cr.execute(query)
        record_ids = [row[0] for row in cr.fetchall()]
        if record_ids:
            raise RuntimeError(f"{label}; record IDs: {record_ids}.")


def _reject_department_conflicts(cr):
    cr.execute(
        """
        SELECT request.id
          FROM sedar_manpower_request AS request
          JOIN hr_department AS department
            ON department.id = request.department_id
         WHERE department.company_id IS NOT NULL
           AND department.company_id != request.company_id
         ORDER BY request.id
        """
    )
    request_ids = [row[0] for row in cr.fetchall()]
    if request_ids:
        raise RuntimeError(
            "Manpower Request departments conflict with their request company; "
            f"request IDs: {request_ids}."
        )


def _reject_shortage_conflicts(cr):
    if not _column_exists(cr, "sedar_marine_service_order", "company_id"):
        raise RuntimeError(
            "Manpower Planning requires the Service Order company migration before upgrade."
        )
    cr.execute(
        """
        SELECT DISTINCT line.id
          FROM sedar_crew_shortage_sedar_manpower_request_line_rel AS relation
          JOIN sedar_manpower_request_line AS line
            ON line.id = relation.sedar_manpower_request_line_id
          JOIN sedar_manpower_request AS request
            ON request.id = line.request_id
          JOIN sedar_crew_shortage AS shortage
            ON shortage.id = relation.sedar_crew_shortage_id
          JOIN sedar_manning_requirement AS requirement
            ON requirement.id = shortage.requirement_id
          JOIN sedar_tug_assignment AS tug_assignment
            ON tug_assignment.id = requirement.tug_assignment_id
          JOIN sedar_marine_service_order AS service_order
            ON service_order.id = tug_assignment.order_id
         WHERE service_order.company_id != request.company_id
         ORDER BY line.id
        """
    )
    line_ids = [row[0] for row in cr.fetchall()]
    if line_ids:
        raise RuntimeError(
            "Manpower Request lines contain crew shortages from another company; "
            f"line IDs: {line_ids}."
        )


def migrate(cr, version):
    """Refuse legacy manpower links that violate company ownership."""
    _reject_department_conflicts(cr)
    _reject_legacy_link_conflicts(cr)
    _reject_shortage_conflicts(cr)

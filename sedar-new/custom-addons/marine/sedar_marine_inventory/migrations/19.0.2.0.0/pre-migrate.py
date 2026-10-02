def _raise_for_invalid_links(cr, label, query):
    cr.execute(query)
    record_ids = [row[0] for row in cr.fetchall()]
    if record_ids:
        raise RuntimeError(f"{label}; record IDs: {record_ids}.")


def _validate_templates(cr):
    cr.execute(
        """
        SELECT template.id
          FROM sedar_inventory_template AS template
          JOIN stock_location AS location
            ON location.id = template.source_location_id
         WHERE location.company_id IS NULL
         ORDER BY template.id
        """
    )
    unowned_template_ids = [row[0] for row in cr.fetchall()]
    if unowned_template_ids:
        raise RuntimeError(
            "Inventory Templates require company-owned source locations before upgrade; "
            f"conflicting template IDs: {unowned_template_ids}."
        )

    cr.execute(
        """
        SELECT DISTINCT template.id
          FROM sedar_inventory_template AS template
          JOIN stock_location AS location
            ON location.id = template.source_location_id
          JOIN sedar_inventory_template_line AS line
            ON line.template_id = template.id
          JOIN product_product AS product
            ON product.id = line.product_id
          JOIN product_template AS product_template
            ON product_template.id = product.product_tmpl_id
         WHERE product_template.company_id IS NOT NULL
           AND product_template.company_id != location.company_id
         ORDER BY template.id
        """
    )
    conflicting_template_ids = [row[0] for row in cr.fetchall()]
    if conflicting_template_ids:
        raise RuntimeError(
            "Inventory Template products conflict with their source-location company; "
            f"template IDs: {conflicting_template_ids}."
        )


def _validate_requirements(cr):
    _raise_for_invalid_links(
        cr,
        "Inventory Requirement products or locations conflict with their Service Order company",
        """
        SELECT requirement.id
          FROM sedar_inventory_requirement requirement
          JOIN sedar_marine_service_order service_order
            ON service_order.id = requirement.order_id
          JOIN stock_location location
            ON location.id = requirement.source_location_id
          JOIN product_product product
            ON product.id = requirement.product_id
          JOIN product_template product_template
            ON product_template.id = product.product_tmpl_id
         WHERE (location.company_id IS NOT NULL
                AND location.company_id != service_order.company_id)
            OR (product_template.company_id IS NOT NULL
                AND product_template.company_id != service_order.company_id)
         ORDER BY requirement.id
        """,
    )


def _validate_fuel_logs(cr):
    _raise_for_invalid_links(
        cr,
        "Fuel-log products or locations conflict with their Marine Operation company",
        """
        SELECT fuel_log.id
          FROM sedar_operation_fuel_log fuel_log
          JOIN sedar_marine_operation operation
            ON operation.id = fuel_log.operation_id
          JOIN sedar_marine_service_order service_order
            ON service_order.id = operation.order_id
          JOIN stock_location source_location
            ON source_location.id = fuel_log.source_location_id
          JOIN stock_location tug_location
            ON tug_location.id = fuel_log.tug_location_id
          JOIN product_product product
            ON product.id = fuel_log.product_id
          JOIN product_template product_template
            ON product_template.id = product.product_tmpl_id
         WHERE (source_location.company_id IS NOT NULL
                AND source_location.company_id != service_order.company_id)
            OR (tug_location.company_id IS NOT NULL
                AND tug_location.company_id != service_order.company_id)
            OR (product_template.company_id IS NOT NULL
                AND product_template.company_id != service_order.company_id)
         ORDER BY fuel_log.id
        """,
    )
    _raise_for_invalid_links(
        cr,
        "Fuel-log stock moves conflict with their Marine Operation company",
        """
        SELECT DISTINCT relation.sedar_operation_fuel_log_id
          FROM sedar_operation_fuel_log_stock_move_rel relation
          JOIN sedar_operation_fuel_log fuel_log
            ON fuel_log.id = relation.sedar_operation_fuel_log_id
          JOIN sedar_marine_operation operation
            ON operation.id = fuel_log.operation_id
          JOIN sedar_marine_service_order service_order
            ON service_order.id = operation.order_id
          JOIN stock_move move
            ON move.id = relation.stock_move_id
         WHERE move.company_id != service_order.company_id
         ORDER BY relation.sedar_operation_fuel_log_id
        """,
    )


def migrate(cr, version):
    """Refuse ambiguous legacy inventory ownership."""
    _validate_templates(cr)
    _validate_requirements(cr)
    _validate_fuel_logs(cr)

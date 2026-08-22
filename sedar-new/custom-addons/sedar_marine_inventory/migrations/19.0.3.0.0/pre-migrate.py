from odoo.exceptions import UserError


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    row = cr.fetchone()
    return bool(row and row[0])


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


def _add_column(cr, table, definition):
    column = definition.split()[0]
    if not _column_exists(cr, table, column):
        cr.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _invalid_ids(cr, query):
    cr.execute(query)
    return [row[0] for row in cr.fetchall()]


def _prepare_contract_columns(cr):
    for definition in (
        "company_id integer",
        "tug_location_id integer",
        "lot_id integer",
        "lifecycle_id integer",
        "legacy_consumed boolean NOT NULL DEFAULT FALSE",
    ):
        _add_column(cr, "sedar_inventory_issue", definition)
    for definition in (
        "sedar_location_role varchar",
        "sedar_tugboat_id integer",
    ):
        _add_column(cr, "stock_location", definition)
    for definition in (
        "sedar_default_storage_location_id integer",
        "sedar_consumption_location_id integer",
        "sedar_disposal_location_id integer",
        "sedar_procurement_inventory_officer_id integer",
    ):
        _add_column(cr, "res_company", definition)
    _add_column(
        cr,
        "product_product",
        "sedar_item_type varchar NOT NULL DEFAULT 'spare_consumable'",
    )


def _validate_legacy_issues(cr):
    invalid_ids = _invalid_ids(
        cr,
        """
        SELECT issue.id
          FROM sedar_inventory_issue issue
          LEFT JOIN stock_move move ON move.id = issue.stock_move_id
          LEFT JOIN stock_location source ON source.id = issue.source_location_id
          LEFT JOIN stock_location destination ON destination.id = move.location_dest_id
          LEFT JOIN sedar_tugboat tugboat ON tugboat.id = issue.tugboat_id
         WHERE issue.lifecycle_id IS NULL
           AND (move.id IS NULL
             OR move.state != 'done'
             OR move.product_id != issue.product_id
             OR move.location_id != issue.source_location_id
             OR move.product_uom_qty != issue.quantity
             OR destination.usage != 'inventory'
             OR source.company_id IS NULL
             OR tugboat.stock_location_id IS NULL)
         ORDER BY issue.id
        """,
    )
    if invalid_ids:
        raise UserError(
            "Legacy Inventory Issues have anomalous or incomplete completed moves; "
            f"affected record IDs: {invalid_ids}."
        )


def _classify_legacy_issues(cr):
    cr.execute(
        """
        UPDATE sedar_inventory_issue issue
           SET company_id = source.company_id,
               tug_location_id = tugboat.stock_location_id,
               legacy_consumed = TRUE
          FROM stock_location source, sedar_tugboat tugboat
         WHERE issue.lifecycle_id IS NULL
           AND source.id = issue.source_location_id
           AND tugboat.id = issue.tugboat_id
           AND (issue.company_id IS DISTINCT FROM source.company_id
             OR issue.tug_location_id IS DISTINCT FROM tugboat.stock_location_id
             OR issue.legacy_consumed IS DISTINCT FROM TRUE)
        """
    )


def _tag_storage_locations(cr):
    cr.execute(
        """
        SELECT DISTINCT location.id
          FROM stock_location location
          JOIN (
                SELECT source_location_id AS location_id FROM sedar_inventory_issue
                UNION
                SELECT source_location_id AS location_id FROM sedar_inventory_template
          ) evidence ON evidence.location_id = location.id
         WHERE location.sedar_location_role IS NOT NULL
           AND location.sedar_location_role != 'storage'
         ORDER BY location.id
        """
    )
    conflicts = [row[0] for row in cr.fetchall()]
    if conflicts:
        raise UserError(
            "Proven Storage locations already have conflicting SEDAR roles; "
            f"affected location IDs: {conflicts}."
        )
    cr.execute(
        """
        UPDATE stock_location location
           SET sedar_location_role = 'storage'
         WHERE location.id IN (
                SELECT source_location_id FROM sedar_inventory_issue
                UNION
                SELECT source_location_id FROM sedar_inventory_template
         )
           AND location.sedar_location_role IS DISTINCT FROM 'storage'
        """
    )


def _tag_tug_locations(cr):
    cr.execute(
        """
        SELECT stock_location_id
          FROM sedar_tugboat
         WHERE stock_location_id IS NOT NULL
         GROUP BY stock_location_id
        HAVING count(*) > 1
         ORDER BY stock_location_id
        """
    )
    duplicates = [row[0] for row in cr.fetchall()]
    if duplicates:
        raise UserError(
            "A Tugboat Stock location is linked to multiple Tugboats; "
            f"affected location IDs: {duplicates}."
        )
    cr.execute(
        """
        SELECT location.id
          FROM stock_location location
          JOIN sedar_tugboat tugboat ON tugboat.stock_location_id = location.id
         WHERE (location.sedar_location_role IS NOT NULL
                AND location.sedar_location_role != 'tug')
            OR (location.sedar_tugboat_id IS NOT NULL
                AND location.sedar_tugboat_id != tugboat.id)
         ORDER BY location.id
        """
    )
    conflicts = [row[0] for row in cr.fetchall()]
    if conflicts:
        raise UserError(
            "Proven Tugboat Stock locations already have conflicting SEDAR links; "
            f"affected location IDs: {conflicts}."
        )
    cr.execute(
        """
        UPDATE stock_location location
           SET sedar_location_role = 'tug',
               sedar_tugboat_id = tugboat.id
          FROM sedar_tugboat tugboat
         WHERE tugboat.stock_location_id = location.id
           AND (location.sedar_location_role IS DISTINCT FROM 'tug'
             OR location.sedar_tugboat_id IS DISTINCT FROM tugboat.id)
        """
    )


def _configure_unambiguous_locations(cr):
    cr.execute(
        """
        WITH storage AS (
            SELECT company_id, min(id) AS location_id
              FROM stock_location
             WHERE sedar_location_role = 'storage'
               AND company_id IS NOT NULL
             GROUP BY company_id
            HAVING count(*) = 1
        )
        UPDATE res_company company
           SET sedar_default_storage_location_id = storage.location_id
          FROM storage
         WHERE company.id = storage.company_id
           AND company.sedar_default_storage_location_id IS NULL
        """
    )
    cr.execute(
        """
        WITH destinations AS (
            SELECT source.company_id, min(move.location_dest_id) AS location_id
              FROM sedar_inventory_issue issue
              JOIN stock_move move ON move.id = issue.stock_move_id
              JOIN stock_location source ON source.id = issue.source_location_id
             WHERE issue.lifecycle_id IS NULL
             GROUP BY source.company_id
            HAVING count(DISTINCT move.location_dest_id) = 1
        )
        UPDATE stock_location location
           SET sedar_location_role = 'consumption'
          FROM destinations
         WHERE location.id = destinations.location_id
           AND location.sedar_location_role IS NULL
        """
    )
    cr.execute(
        """
        WITH destinations AS (
            SELECT source.company_id, min(move.location_dest_id) AS location_id
              FROM sedar_inventory_issue issue
              JOIN stock_move move ON move.id = issue.stock_move_id
              JOIN stock_location source ON source.id = issue.source_location_id
             WHERE issue.lifecycle_id IS NULL
             GROUP BY source.company_id
            HAVING count(DISTINCT move.location_dest_id) = 1
        )
        UPDATE res_company company
           SET sedar_consumption_location_id = destinations.location_id
          FROM destinations
          JOIN stock_location location ON location.id = destinations.location_id
         WHERE company.id = destinations.company_id
           AND company.sedar_consumption_location_id IS NULL
           AND location.sedar_location_role = 'consumption'
        """
    )


def _classify_existing_items(cr):
    if _table_exists(cr, "sedar_operation_fuel_log"):
        cr.execute(
            """
            UPDATE product_product product
               SET sedar_item_type = 'fuel_lubricant'
             WHERE product.id IN (
                    SELECT DISTINCT product_id FROM sedar_operation_fuel_log
             )
               AND product.sedar_item_type != 'fuel_lubricant'
            """
        )


def migrate(cr, version):
    """Preserve legacy one-step issues and add only evidence-backed ownership tags."""
    if not _table_exists(cr, "sedar_inventory_issue"):
        return
    _prepare_contract_columns(cr)
    _validate_legacy_issues(cr)
    _classify_legacy_issues(cr)
    _tag_storage_locations(cr)
    _tag_tug_locations(cr)
    _configure_unambiguous_locations(cr)
    _classify_existing_items(cr)

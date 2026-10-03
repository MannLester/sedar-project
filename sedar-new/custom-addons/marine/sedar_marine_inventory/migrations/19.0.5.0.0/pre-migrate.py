from psycopg2 import sql


def migrate(cr, version):
    cr.execute(
        """
        SELECT conname
          FROM pg_constraint
         WHERE conrelid = 'stock_location'::regclass
           AND contype = 'u'
           AND pg_get_constraintdef(oid) = 'UNIQUE (sedar_tugboat_id)'
        """
    )
    for (constraint_name,) in cr.fetchall():
        cr.execute(
            sql.SQL("ALTER TABLE stock_location DROP CONSTRAINT {}").format(
                sql.Identifier(constraint_name)
            )
        )
    cr.execute(
        """
        UPDATE product_product
           SET sedar_item_type = 'spare_part'
         WHERE sedar_item_type = 'spare_consumable'
           AND id IN (
               SELECT DISTINCT product_id
                 FROM sedar_maintenance_part_line
                WHERE product_id IS NOT NULL
           )
        """
    )
    cr.execute(
        """
        UPDATE product_product
           SET sedar_item_type = 'consumable_store'
         WHERE sedar_item_type = 'spare_consumable'
        """
    )

def migrate(cr, version):
    """Backfill the durable inverse without rewriting legacy singular history."""
    cr.execute(
        """
        UPDATE purchase_order AS po
           SET sedar_purchase_request_id = request.id
          FROM sedar_purchase_request AS request
         WHERE request.purchase_order_id = po.id
           AND po.sedar_purchase_request_id IS NULL
           AND po.company_id = request.company_id
        """
    )

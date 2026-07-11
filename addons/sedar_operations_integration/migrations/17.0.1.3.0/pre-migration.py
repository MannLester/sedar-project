def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE sedar_document_control
        ADD COLUMN IF NOT EXISTS legacy_renewal_owner varchar
        """
    )
    cr.execute(
        """
        UPDATE sedar_document_control
        SET legacy_renewal_owner = renewal_owner
        WHERE renewal_owner IS NOT NULL
          AND renewal_owner !~ '^[0-9]+$'
        """
    )
    cr.execute(
        """
        UPDATE sedar_document_control
        SET renewal_owner = NULL
        WHERE renewal_owner IS NOT NULL
          AND renewal_owner !~ '^[0-9]+$'
        """
    )

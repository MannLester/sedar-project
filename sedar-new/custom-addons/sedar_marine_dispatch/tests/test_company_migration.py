import importlib.util
from pathlib import Path

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDispatchCompanyMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"].create({"name": "Dispatch Migration Client"})
        port = cls.env["sedar.marine.port"].create({
            "name": "Dispatch Migration Port", "code": "DISP-MIG",
        })
        service = cls.env["sedar.marine.service.type"].create({
            "name": "Dispatch Migration Assist",
            "code": "DISP-MIG",
            "pricing_basis": "per_service",
        })
        tug_class = cls.env["sedar.tug.class"].create({"name": "Dispatch Migration Tug"})
        tug = cls.env["sedar.tugboat"].create({
            "name": "Dispatch Migration Tug",
            "registration_number": "DISP-MIG-001",
            "tug_class_id": tug_class.id,
        })
        order_values = {
            "client_id": partner.id,
            "service_type_id": service.id,
            "scope_of_work": "Validate legacy dispatch links.",
            "port_id": port.id,
            "requested_start": fields.Datetime.now(),
        }
        cls.order_a = cls.env["sedar.marine.service.order"].create({
            **order_values, "assisted_vessel_name": "MV Dispatch Migration A",
        })
        cls.order_b = cls.env["sedar.marine.service.order"].create({
            **order_values, "assisted_vessel_name": "MV Dispatch Migration B",
        })
        cls.assignment_a = cls.env["sedar.tug.assignment"].create({
            "order_id": cls.order_a.id, "tugboat_id": tug.id,
        })
        cls.assignment_b = cls.env["sedar.tug.assignment"].create({
            "order_id": cls.order_b.id, "tugboat_id": tug.id,
        })
        cls.operation = cls.env["sedar.marine.operation"].create({"order_id": cls.order_a.id})
        cls.operation_tug = cls.env["sedar.marine.operation.tug"].create({
            "operation_id": cls.operation.id,
            "tug_assignment_id": cls.assignment_a.id,
            "tugboat_id": tug.id,
        })

    def test_upgrade_rejects_legacy_operation_tug_from_another_order(self):
        migration_path = (
            Path(get_module_path("sedar_marine_operations"))
            / "migrations/19.0.2.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_dispatch_company_pre_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.env.cr.execute(
            "UPDATE sedar_marine_operation_tug SET tug_assignment_id = %s WHERE id = %s",
            (self.assignment_b.id, self.operation_tug.id),
        )

        with self.assertRaisesRegex(UserError, "legacy dispatch links conflict"):
            migration._validate_nested_dispatch_links(self.env.cr)

        self.env.cr.execute(
            "UPDATE sedar_marine_operation_tug SET tug_assignment_id = %s WHERE id = %s",
            (self.assignment_a.id, self.operation_tug.id),
        )

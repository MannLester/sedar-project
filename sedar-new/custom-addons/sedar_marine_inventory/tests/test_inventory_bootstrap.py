from odoo.addons.sedar_marine_inventory import hooks
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInventoryBootstrap(TransactionCase):
    def _company_with_two_warehouses(self, suffix):
        company = self.env["res.company"].create({
            "name": f"Bootstrap {suffix} Company",
        })
        warehouse_model = self.env["stock.warehouse"].with_company(company)
        first = warehouse_model.create({
            "name": f"Bootstrap {suffix} First",
            "code": f"{suffix}1",
            "company_id": company.id,
        })
        second = warehouse_model.create({
            "name": f"Bootstrap {suffix} Second",
            "code": f"{suffix}2",
            "company_id": company.id,
        })
        company_env = self.env["res.company"].with_company(company).env
        return company_env, company, first, second

    def test_multiple_warehouses_without_explicit_storage_are_rejected(self):
        company_env, company, first, second = self._company_with_two_warehouses(
            "AMB"
        )
        warehouses = company_env["stock.warehouse"].search([
            ("company_id", "=", company.id),
        ])
        roles_before = {
            warehouse.id: warehouse.lot_stock_id.sedar_location_role
            for warehouse in warehouses
        }

        with self.assertRaises(UserError) as raised:
            hooks._resolve_storage_location(company_env)

        message = str(raised.exception)
        self.assertIn(str(first.id), message)
        self.assertIn(str(second.id), message)
        self.assertIn("Default SEDAR Storage Location", message)
        self.assertFalse(company.sedar_default_storage_location_id)
        self.assertEqual(
            roles_before,
            {
                warehouse.id: warehouse.lot_stock_id.sedar_location_role
                for warehouse in warehouses
            },
        )

    def test_configured_storage_is_deterministic_with_multiple_warehouses(self):
        company_env, company, first, second = self._company_with_two_warehouses(
            "DET"
        )
        selected = second.lot_stock_id
        selected.sedar_location_role = "storage"
        company.sedar_default_storage_location_id = selected

        first_result = hooks._resolve_storage_location(company_env)
        second_result = hooks._resolve_storage_location(company_env)

        self.assertEqual(first_result, selected)
        self.assertEqual(second_result, selected)
        self.assertFalse(first.lot_stock_id.sedar_location_role)

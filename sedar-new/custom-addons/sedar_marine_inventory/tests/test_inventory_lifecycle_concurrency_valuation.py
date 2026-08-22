from odoo import Command, api
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.float_utils import float_is_zero
from psycopg2.errors import LockNotAvailable


@tagged("post_install", "-at_install")
class TestInventoryLifecycleQuantityValuation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.precise_unit = cls.env["uom.uom"].create(
            {
                "name": "Lifecycle Hundredth Unit",
                "relative_uom_id": cls.unit.id,
                "relative_factor": 1.0,
                "rounding": 0.01,
            }
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.storage = cls.warehouse.lot_stock_id
        cls.storage.sedar_location_role = "storage"
        cls.consumption = cls.env["stock.location"].create(
            {
                "name": "Lifecycle Valuation Consumption",
                "usage": "inventory",
                "location_id": cls.warehouse.view_location_id.id,
                "company_id": cls.company.id,
                "sedar_location_role": "consumption",
                "valuation_account_id": cls.company.expense_account_id.id,
            }
        )
        cls.disposal = cls.env["stock.location"].create(
            {
                "name": "Lifecycle Valuation Disposal",
                "usage": "inventory",
                "location_id": cls.warehouse.view_location_id.id,
                "company_id": cls.company.id,
                "sedar_location_role": "disposal",
                "valuation_account_id": cls.company.expense_account_id.id,
            }
        )
        cls.tug_class = cls.env["sedar.tug.class"].create(
            {"name": "Lifecycle Concurrency Valuation Tug Class"}
        )
        cls.tug = cls.env["sedar.tugboat"].create(
            {
                "name": "Lifecycle Concurrency Valuation Tug",
                "registration_number": "LIFECYCLE-CONCURRENCY-VALUATION",
                "tug_class_id": cls.tug_class.id,
                "company_id": cls.company.id,
            }
        )
        cls.tug_location = cls.env["stock.location"].create(
            {
                "name": "Lifecycle Concurrency Valuation Tug Stock",
                "usage": "internal",
                "location_id": cls.warehouse.view_location_id.id,
                "company_id": cls.company.id,
                "sedar_location_role": "tug",
                "sedar_tugboat_id": cls.tug.id,
            }
        )
        cls.tug.stock_location_id = cls.tug_location
        inventory_group = cls.env.ref(
            "sedar_marine_inventory.group_marine_inventory_manager"
        )
        cls.officer = cls.env["res.users"].create(
            {
                "name": "Lifecycle Concurrency Valuation Officer",
                "login": "lifecycle.concurrency.valuation@test.example",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [
                    Command.set([cls.env.ref("base.group_user").id, inventory_group.id])
                ],
            }
        )
        cls.company.write(
            {
                "sedar_procurement_inventory_officer_id": cls.officer.id,
                "sedar_default_storage_location_id": cls.storage.id,
                "sedar_consumption_location_id": cls.consumption.id,
                "sedar_disposal_location_id": cls.disposal.id,
            }
        )
        cls.precise_product = cls.env["product.product"].create(
            {
                "name": "Lifecycle Rounded Spare",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.precise_unit.id,
                "default_code": "LIFECYCLE-ROUNDED-SPARE",
                "sedar_inventory_item": True,
                "sedar_item_type": "spare_consumable",
            }
        )
        cls.valuation_category = cls.env["product.category"].create(
            {
                "name": "Lifecycle Standard Automated Valuation",
                "property_cost_method": "standard",
                "property_valuation": "real_time",
            }
        )
        cls.valuation_product = cls.env["product.product"].create(
            {
                "name": "Lifecycle Valued Spare",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.unit.id,
                "categ_id": cls.valuation_category.id,
                "standard_price": 25.0,
                "default_code": "LIFECYCLE-VALUED-SPARE",
                "sedar_inventory_item": True,
                "sedar_item_type": "spare_consumable",
            }
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.precise_product, cls.storage, 10
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.valuation_product, cls.storage, 10
        )

    def _issue(self, product, quantity):
        return (
            self.env["sedar.inventory.issue"]
            .with_user(self.officer)
            ._issue_to_tug(
                product,
                self.tug,
                quantity,
                "Concurrency and valuation test",
                self.storage,
            )
        )

    def test_computed_quantity_clamps_a_legacy_rounding_residue(self):
        lifecycle = self._issue(self.precise_product, 1).lifecycle_id.with_user(
            self.officer
        )
        move = lifecycle._create_done_stock_move(
            lifecycle.product_id,
            0.996,
            lifecycle.tug_location_id,
            lifecycle.company_id.sedar_consumption_location_id,
            "Historical rounded close",
            lifecycle.company_id,
        )
        lifecycle._create_event("consume", 0.996, "Historical rounded close", move)
        lifecycle.invalidate_recordset(["open_qty", "state"])

        self.assertEqual(lifecycle.open_qty, 0)
        self.assertEqual(lifecycle.state, "closed")

    def test_last_close_normalizes_event_move_and_physical_quantity(self):
        lifecycle = self._issue(self.precise_product, 1).lifecycle_id.with_user(
            self.officer
        )

        lifecycle.action_consume(0.996, "Close within UoM precision")

        event = lifecycle.event_ids
        self.assertEqual(event.quantity, 1)
        self.assertEqual(event.stock_move_id.quantity, 1)
        self.assertEqual(lifecycle.open_qty, 0)
        self.assertEqual(lifecycle.state, "closed")
        physical = lifecycle._available_quantity(
            lifecycle.product_id, lifecycle.tug_location_id
        )
        self.assertTrue(
            float_is_zero(
                physical, precision_rounding=lifecycle.product_uom_id.rounding
            )
        )

    def test_reconciliation_uses_shared_tug_balance_and_flags_unlinked_move(self):
        first = self._issue(self.precise_product, 2).lifecycle_id
        second = self._issue(self.precise_product, 3).lifecycle_id

        self.assertEqual(first.reconciliation_state, "reconciled")
        self.assertEqual(second.reconciliation_state, "reconciled")

        first._create_done_stock_move(
            first.product_id,
            1,
            first.tug_location_id,
            first.company_id.sedar_consumption_location_id,
            "Unlinked out-of-band tug movement",
            first.company_id,
        )
        (first | second).invalidate_recordset(["reconciliation_state"])

        self.assertEqual(first.reconciliation_state, "warning")
        self.assertEqual(second.reconciliation_state, "warning")

    def test_standard_valuation_boundary_is_owned_by_odoo_stock(self):
        returned = self._issue(self.valuation_product, 1).lifecycle_id.with_user(
            self.officer
        )
        issue_move = returned.issue_move_id
        returned.action_return(1, "Unused valued stock")
        return_move = returned.event_ids.stock_move_id

        self.assertFalse(issue_move.is_valued)
        self.assertFalse(issue_move.account_move_id)
        self.assertEqual(issue_move.value, 0)
        self.assertFalse(return_move.is_valued)
        self.assertFalse(return_move.account_move_id)
        self.assertEqual(return_move.value, 0)

        consumed = self._issue(self.valuation_product, 2).lifecycle_id.with_user(
            self.officer
        )
        consumed.action_consume(2, "Valued maintenance consumption")
        consume_move = consumed.event_ids.stock_move_id
        disposed = self._issue(self.valuation_product, 1).lifecycle_id.with_user(
            self.officer
        )
        disposed.action_dispose(1, "Valued damaged stock")
        disposal_move = disposed.event_ids.stock_move_id

        for move, expected_value in ((consume_move, 50), (disposal_move, 25)):
            self.assertTrue(move.is_valued)
            self.assertEqual(move.value, expected_value)
            self.assertEqual(move.account_move_id.state, "posted")
            self.assertEqual(
                set(move.account_move_id.line_ids.account_id),
                {
                    self.company.expense_account_id,
                    self.company.account_stock_valuation_id,
                },
            )


@tagged("post_install", "-at_install")
class TestInventoryLifecycleConcurrency(TransactionCase):
    def _create_committed_fixture(self):
        with self.registry.cursor() as cr:
            env = api.Environment(cr, self.env.ref("base.user_admin").id, {})
            company = env["res.company"].create(
                {"name": "Lifecycle Committed Concurrency Company"}
            )
            warehouse = (
                env["stock.warehouse"]
                .with_company(company)
                .create(
                    {
                        "name": "Lifecycle Concurrency Warehouse",
                        "code": "LCWH",
                        "company_id": company.id,
                    }
                )
            )
            storage = warehouse.lot_stock_id
            storage.sedar_location_role = "storage"
            consumption = (
                env["stock.location"]
                .with_company(company)
                .create(
                    {
                        "name": "Lifecycle Concurrency Consumption",
                        "usage": "inventory",
                        "location_id": warehouse.view_location_id.id,
                        "company_id": company.id,
                        "sedar_location_role": "consumption",
                    }
                )
            )
            tug_class = env["sedar.tug.class"].create(
                {"name": "Lifecycle Committed Concurrency Tug Class"}
            )
            tug = (
                env["sedar.tugboat"]
                .with_company(company)
                .create(
                    {
                        "name": "Lifecycle Committed Concurrency Tug",
                        "registration_number": "LIFECYCLE-COMMITTED-CONCURRENCY",
                        "tug_class_id": tug_class.id,
                        "company_id": company.id,
                    }
                )
            )
            tug_location = (
                env["stock.location"]
                .with_company(company)
                .create(
                    {
                        "name": "Lifecycle Committed Concurrency Tug Stock",
                        "usage": "internal",
                        "location_id": warehouse.view_location_id.id,
                        "company_id": company.id,
                        "sedar_location_role": "tug",
                        "sedar_tugboat_id": tug.id,
                    }
                )
            )
            tug.stock_location_id = tug_location
            inventory_group = env.ref(
                "sedar_marine_inventory.group_marine_inventory_manager"
            )
            officer = (
                env["res.users"]
                .with_company(company)
                .create(
                    {
                        "name": "Lifecycle Committed Concurrency Officer",
                        "login": "lifecycle.committed.concurrency@test.example",
                        "company_id": company.id,
                        "company_ids": [Command.set(company.ids)],
                        "group_ids": [
                            Command.set(
                                [env.ref("base.group_user").id, inventory_group.id]
                            )
                        ],
                    }
                )
            )
            company.write(
                {
                    "sedar_procurement_inventory_officer_id": officer.id,
                    "sedar_default_storage_location_id": storage.id,
                    "sedar_consumption_location_id": consumption.id,
                }
            )
            product = (
                env["product.product"]
                .with_company(company)
                .create(
                    {
                        "name": "Lifecycle Committed Concurrency Spare",
                        "type": "consu",
                        "is_storable": True,
                        "company_id": company.id,
                        "default_code": "LIFECYCLE-COMMITTED-CONCURRENCY-SPARE",
                        "sedar_inventory_item": True,
                        "sedar_item_type": "spare_consumable",
                    }
                )
            )
            env["stock.quant"].with_company(company)._update_available_quantity(
                product, storage, 1
            )
            issue = (
                env["sedar.inventory.issue"]
                .with_user(officer)
                .with_company(company)
                ._issue_to_tug(
                    product,
                    tug,
                    1,
                    "Committed concurrency fixture",
                    storage,
                )
            )
            fixture = {
                "company_id": company.id,
                "officer_id": officer.id,
                "lifecycle_id": issue.lifecycle_id.id,
            }
            cr.commit()
        return fixture

    def test_competing_close_waits_then_revalidates_after_lock_release(self):
        fixture = self._create_committed_fixture()
        context = {"allowed_company_ids": [fixture["company_id"]]}

        with self.registry.cursor() as winning_cr:
            winning_env = api.Environment(winning_cr, fixture["officer_id"], context)
            winning = winning_env["sedar.inventory.lifecycle"].browse(
                fixture["lifecycle_id"]
            )
            winning._lock_and_reload()

            with self.registry.cursor() as competing_cr:
                competing_cr.execute("SET LOCAL lock_timeout = '100ms'")
                with self.assertRaises(LockNotAvailable):
                    competing_cr.execute(
                        """
                        SELECT id
                          FROM sedar_inventory_lifecycle
                         WHERE id = %s
                           FOR UPDATE
                        """,
                        [fixture["lifecycle_id"]],
                    )
                competing_cr.rollback()

            winning.action_consume(1, "Winning close")
            winning_cr.commit()

        with self.registry.cursor() as retry_cr:
            retry_env = api.Environment(retry_cr, fixture["officer_id"], context)
            retry = retry_env["sedar.inventory.lifecycle"].browse(
                fixture["lifecycle_id"]
            )
            with self.assertRaises(UserError):
                retry.action_consume(1, "Retry after competing close")
            retry_cr.rollback()

        with self.registry.cursor() as verify_cr:
            verify_env = api.Environment(verify_cr, fixture["officer_id"], context)
            lifecycle = verify_env["sedar.inventory.lifecycle"].browse(
                fixture["lifecycle_id"]
            )
            self.assertEqual(lifecycle.state, "closed")
            self.assertEqual(lifecycle.open_qty, 0)
            self.assertEqual(len(lifecycle.event_ids), 1)

import importlib.util
from pathlib import Path

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


def _load_tugboat_company_migration():
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "19.0.3.0.0"
        / "pre-migrate.py"
    )
    spec = importlib.util.spec_from_file_location(
        "sedar_tugboat_company_migration", migration_path
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


@tagged("post_install", "-at_install")
class TestServiceOrderCompanyOwnership(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Other Marine Company"})
        cls.partner_a = cls.env["res.partner"].create({
            "name": "Company A Client", "company_id": cls.company_a.id,
        })
        cls.partner_b = cls.env["res.partner"].create({
            "name": "Company B Client", "company_id": cls.company_b.id,
        })
        cls.port = cls.env["sedar.marine.port"].create({"name": "Company Test Port", "code": "CTP"})
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Company Test Assist", "code": "COMPANY-TEST",
            "pricing_basis": "per_service",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Company Test Tug"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Company Test Tug", "registration_number": "COMPANY-TEST-001",
            "tug_class_id": cls.tug_class.id,
        })
        cls.rank = cls.env["sedar.crew.rank"].create({
            "name": "Company Test Master", "code": "COMPANY-MASTER",
        })
        employee = cls.env["hr.employee"].create({
            "name": "Company Test Employee", "company_id": cls.company_a.id,
        })
        cls.profile = cls.env["sedar.crew.profile"].create({
            "employee_id": employee.id, "employee_number": "COMPANY-EMP-001",
            "rank_id": cls.rank.id,
        })
        cls.order_a = cls._create_order(cls.company_a, cls.partner_a, "A")
        cls.order_b = cls._create_order(cls.company_b, cls.partner_b, "B")

    @classmethod
    def _create_order(cls, company, partner, suffix):
        return cls.env["sedar.marine.service.order"].with_company(company).create({
            "company_id": company.id,
            "client_id": partner.id,
            "assisted_vessel_name": f"MV Company {suffix}",
            "service_type_id": cls.service.id,
            "scope_of_work": "Company ownership test",
            "port_id": cls.port.id,
            "requested_start": fields.Datetime.now(),
        })

    def test_company_defaults_and_is_immutable(self):
        order = self.env["sedar.marine.service.order"].with_company(self.company_b).create({
            "client_id": self.partner_b.id,
            "assisted_vessel_name": "MV Company Default",
            "service_type_id": self.service.id,
            "scope_of_work": "Company default test",
            "port_id": self.port.id,
            "requested_start": fields.Datetime.now(),
        })
        self.assertEqual(order.company_id, self.company_b)
        with self.assertRaisesRegex(ValidationError, "cannot be changed"):
            order.write({"company_id": self.company_a.id})

    def test_tugboat_company_defaults_and_is_immutable(self):
        tugboat = self.env["sedar.tugboat"].with_company(self.company_b).create({
            "name": "Company B Tugboat",
            "registration_number": "COMPANY-TEST-B-001",
            "tug_class_id": self.tug_class.id,
        })
        self.assertEqual(tugboat.company_id, self.company_b)
        with self.assertRaisesRegex(ValidationError, "cannot be changed"):
            tugboat.write({"company_id": self.company_a.id})

    def test_company_owned_partner_cannot_cross_company(self):
        with self.assertRaises(UserError):
            self.env["sedar.marine.service.order"].with_company(self.company_a).create({
                "company_id": self.company_a.id,
                "client_id": self.partner_b.id,
                "assisted_vessel_name": "MV Wrong Company",
                "service_type_id": self.service.id,
                "scope_of_work": "Must be rejected",
                "port_id": self.port.id,
                "requested_start": fields.Datetime.now(),
            })

    def test_operational_descendants_inherit_company(self):
        tug_assignment = self.env["sedar.tug.assignment"].create({
            "order_id": self.order_a.id, "tugboat_id": self.tug.id,
        })
        requirement = self.env["sedar.manning.requirement"].create({
            "tug_assignment_id": tug_assignment.id,
            "rank_id": self.rank.id,
        })
        crew_assignment = self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement.id,
            "crew_profile_id": self.profile.id,
        })
        shortage = self.env["sedar.crew.shortage"].create({
            "requirement_id": requirement.id,
            "reason": "no_qualified",
        })
        self.assertEqual(tug_assignment.company_id, self.company_a)
        self.assertEqual(requirement.company_id, self.company_a)
        self.assertEqual(crew_assignment.company_id, self.company_a)
        self.assertEqual(shortage.company_id, self.company_a)

    def test_tug_assignment_rejects_tugboat_from_another_company(self):
        tugboat_b = self.env["sedar.tugboat"].with_company(self.company_b).create({
            "name": "Company B Assignment Tug",
            "registration_number": "COMPANY-TEST-B-ASSIGN",
            "tug_class_id": self.tug_class.id,
        })
        with self.assertRaisesRegex(UserError, "belongs to another company"):
            self.env["sedar.tug.assignment"].create({
                "order_id": self.order_a.id,
                "tugboat_id": tugboat_b.id,
            })

    def test_global_rule_hides_other_company(self):
        user = self.env["res.users"].create({
            "name": "Company A Operations User",
            "login": "company-a-operations@example.com",
            "company_id": self.company_a.id,
            "company_ids": [Command.set([self.company_a.id])],
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
        })
        visible = self.env["sedar.marine.service.order"].with_user(user).search([])
        self.assertIn(self.order_a, visible)
        self.assertNotIn(self.order_b, visible)

        tugboat_b = self.env["sedar.tugboat"].with_company(self.company_b).create({
            "name": "Company B Hidden Tug",
            "registration_number": "COMPANY-TEST-B-HIDDEN",
            "tug_class_id": self.tug_class.id,
        })
        visible_tugboats = self.env["sedar.tugboat"].with_user(user).search([])
        self.assertIn(self.tug, visible_tugboats)
        self.assertNotIn(tugboat_b, visible_tugboats)

    def test_tugboat_migration_infers_company_from_service_order(self):
        self.env["sedar.tug.assignment"].create({
            "order_id": self.order_a.id,
            "tugboat_id": self.tug.id,
        })
        self.env.cr.execute(
            "ALTER TABLE sedar_tugboat ALTER COLUMN company_id DROP NOT NULL"
        )
        self.env.cr.execute(
            "UPDATE sedar_tugboat SET company_id = NULL WHERE id = %s",
            (self.tug.id,),
        )

        migration = _load_tugboat_company_migration()
        migration.migrate(self.env.cr, "19.0.2.0.0")
        migration.migrate(self.env.cr, "19.0.2.0.0")

        self.tug.invalidate_recordset(["company_id"])
        self.assertEqual(self.tug.company_id, self.company_a)

    def test_tugboat_migration_rejects_conflicting_company_evidence(self):
        tugboat_b = self.env["sedar.tugboat"].with_company(self.company_b).create({
            "name": "Conflicting Company Tug",
            "registration_number": "COMPANY-TEST-CONFLICT",
            "tug_class_id": self.tug_class.id,
        })
        self.env.cr.execute(
            """
            INSERT INTO sedar_tug_assignment
                (order_id, tugboat_id, state, completion_state, create_uid, write_uid,
                 create_date, write_date)
            VALUES (%s, %s, 'planned', 'pending', %s, %s, NOW(), NOW())
            """,
            (self.order_a.id, tugboat_b.id, self.env.uid, self.env.uid),
        )

        with self.assertRaisesRegex(UserError, "Tugboat company evidence conflicts"):
            _load_tugboat_company_migration().migrate(self.env.cr, "19.0.2.0.0")

    def test_tugboat_migration_rejects_missing_company_evidence(self):
        tugboat = self.env["sedar.tugboat"].create({
            "name": "No Evidence Tug",
            "registration_number": "COMPANY-TEST-NO-EVIDENCE",
            "tug_class_id": self.tug_class.id,
        })
        self.env.cr.execute(
            "ALTER TABLE sedar_tugboat ALTER COLUMN company_id DROP NOT NULL"
        )
        self.env.cr.execute(
            "UPDATE sedar_tugboat SET company_id = NULL WHERE id = %s",
            (tugboat.id,),
        )

        with self.assertRaisesRegex(UserError, "company evidence is missing"):
            _load_tugboat_company_migration().migrate(self.env.cr, "19.0.2.0.0")

    def test_migration_infers_company_from_company_owned_client(self):
        migration_path = (
            Path(__file__).parents[1]
            / "migrations"
            / "19.0.2.0.0"
            / "pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location("sedar_service_order_company_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.env.cr.execute(
            "ALTER TABLE sedar_marine_service_order ALTER COLUMN company_id DROP NOT NULL"
        )
        self.env.cr.execute(
            "UPDATE sedar_marine_service_order SET company_id = NULL WHERE id = %s",
            (self.order_b.id,),
        )
        migration.migrate(self.env.cr, "19.0.1.0.0")
        self.order_b.invalidate_recordset(["company_id"])
        self.assertEqual(self.order_b.company_id, self.company_b)

    def test_migration_rejects_conflicting_company_evidence(self):
        migration_path = (
            Path(__file__).parents[1]
            / "migrations"
            / "19.0.2.0.0"
            / "pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_service_order_company_conflict_migration", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.env.cr.execute(
            "ALTER TABLE sedar_marine_service_order ALTER COLUMN company_id DROP NOT NULL"
        )
        self.env.cr.execute(
            """
            UPDATE sedar_marine_service_order
               SET company_id = NULL, contact_id = %s
             WHERE id = %s
            """,
            (self.partner_a.id, self.order_b.id),
        )
        with self.assertRaisesRegex(UserError, "company-owned evidence conflicts"):
            migration.migrate(self.env.cr, "19.0.1.0.0")
        self.env.cr.execute(
            """
            UPDATE sedar_marine_service_order
               SET company_id = %s, contact_id = NULL
             WHERE id = %s
            """,
            (self.company_b.id, self.order_b.id),
        )
        self.env.cr.execute(
            "ALTER TABLE sedar_marine_service_order ALTER COLUMN company_id SET NOT NULL"
        )

    def test_migration_fallback_is_repeatable(self):
        migration_path = (
            Path(__file__).parents[1]
            / "migrations"
            / "19.0.2.0.0"
            / "pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_service_order_company_fallback_migration", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        shared_partner = self.env["res.partner"].create({"name": "Shared Migration Client"})
        order = self._create_order(self.company_a, shared_partner, "Fallback")
        self.env.cr.execute(
            "ALTER TABLE sedar_marine_service_order ALTER COLUMN company_id DROP NOT NULL"
        )
        self.env.cr.execute(
            "UPDATE sedar_marine_service_order SET company_id = NULL WHERE id = %s",
            (order.id,),
        )

        migration.migrate(self.env.cr, "19.0.1.0.0")
        migration.migrate(self.env.cr, "19.0.1.0.0")

        order.invalidate_recordset(["company_id"])
        self.assertEqual(order.company_id, self.env.ref("base.main_company"))

import importlib.util
from pathlib import Path

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestManpowerCompanyOwnership(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Other Manpower Company"})
        cls.department_b = cls.env["hr.department"].create({
            "name": "Marine Operations B",
            "company_id": cls.company_b.id,
        })
        cls.partner_b = cls.env["res.partner"].create({
            "name": "Company B Manpower Client",
            "company_id": cls.company_b.id,
        })
        cls.port = cls.env["sedar.marine.port"].create({
            "name": "Manpower Company Port",
            "code": "MCP",
        })
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Manpower Company Assist",
            "code": "MCA",
            "pricing_basis": "per_service",
        })
        tug_class = cls.env["sedar.tug.class"].create({"name": "Manpower Company Tug"})
        cls.tugboat = cls.env["sedar.tugboat"].create({
            "name": "Manpower Company Tug",
            "registration_number": "MCP-TUG-001",
            "tug_class_id": tug_class.id,
        })
        cls.rank = cls.env["sedar.crew.rank"].create({
            "name": "Manpower Company Master",
            "code": "MCP-MASTER",
        })
        cls.shortage_b = cls._create_shortage(cls.company_b, cls.partner_b)

    @classmethod
    def _create_shortage(cls, company, partner):
        order = cls.env["sedar.marine.service.order"].with_company(company).create({
            "company_id": company.id,
            "client_id": partner.id,
            "assisted_vessel_name": "MV Manpower Company",
            "service_type_id": cls.service.id,
            "scope_of_work": "Verify company-owned manpower handoff.",
            "port_id": cls.port.id,
            "requested_start": fields.Datetime.now(),
        })
        tug_assignment = cls.env["sedar.tug.assignment"].create({
            "order_id": order.id,
            "tugboat_id": cls.tugboat.id,
        })
        requirement = cls.env["sedar.manning.requirement"].create({
            "tug_assignment_id": tug_assignment.id,
            "rank_id": cls.rank.id,
        })
        return cls.env["sedar.crew.shortage"].create({
            "requirement_id": requirement.id,
            "reason": "no_qualified",
            "root_cause": "permanent_headcount",
            "review_state": "escalated",
        })

    def _load_migration(self):
        migration_path = (
            Path(__file__).parents[1]
            / "migrations"
            / "19.0.2.0.0"
            / "pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_manpower_company_pre_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        return migration

    def test_shortage_action_inherits_company_and_is_company_scoped(self):
        action = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": self.shortage_b.id,
            "action_type": "manpower",
        })
        self.assertEqual(action.company_id, self.company_b)

        user_a = new_test_user(
            self.env,
            login="company-a-crewing@example.com",
            groups="sedar_manpower_planning.group_crewing_officer",
            company_id=self.company_a.id,
            company_ids=[Command.set([self.company_a.id])],
        )
        self.assertFalse(
            self.env["sedar.crew.shortage.action"].with_user(user_a).search([
                ("id", "=", action.id),
            ])
        )

    def test_shortage_handoff_uses_service_order_company(self):
        action = self.shortage_b.with_company(self.company_a).action_create_manpower_request()
        request = self.env["sedar.manpower.request"].browse(action["res_id"])

        self.assertEqual(request.company_id, self.company_b)
        self.assertEqual(request.department_id, self.department_b)
        self.assertEqual(request.line_ids.company_id, self.company_b)
        self.assertEqual(request.line_ids.shortage_ids, self.shortage_b)

    def test_manpower_line_rejects_foreign_company_shortage(self):
        department_a = self.env["hr.department"].create({
            "name": "Marine Operations A",
            "company_id": self.company_a.id,
        })
        request_a = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Cross-company rejection test.",
        })
        with self.assertRaises(ValidationError):
            self.env["sedar.manpower.request.line"].create({
                "request_id": request_a.id,
                "crew_rank_id": self.rank.id,
                "required_date": fields.Date.today(),
                "shortage_ids": [Command.link(self.shortage_b.id)],
            })

    def test_upgrade_rejects_foreign_company_department(self):
        department_a = self.env["hr.department"].create({
            "name": "Legacy Marine Department A",
            "company_id": self.company_a.id,
        })
        request = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Legacy department migration test.",
        })
        self.env.cr.execute(
            "UPDATE hr_department SET company_id = %s WHERE id = %s",
            (self.company_b.id, department_a.id),
        )

        with self.assertRaisesRegex(RuntimeError, f"request IDs: \\[{request.id}\\]"):
            self._load_migration().migrate(self.env.cr, "19.0.1.0.0")

    def test_upgrade_rejects_foreign_company_shortage_relation(self):
        department_a = self.env["hr.department"].create({
            "name": "Legacy Shortage Department A",
            "company_id": self.company_a.id,
        })
        request = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Legacy shortage relation migration test.",
        })
        line = self.env["sedar.manpower.request.line"].create({
            "request_id": request.id,
            "crew_rank_id": self.rank.id,
            "required_date": fields.Date.today(),
        })
        self.env.cr.execute(
            """
            INSERT INTO sedar_crew_shortage_sedar_manpower_request_line_rel
                        (sedar_manpower_request_line_id, sedar_crew_shortage_id)
                 VALUES (%s, %s)
            """,
            (line.id, self.shortage_b.id),
        )

        with self.assertRaisesRegex(RuntimeError, f"line IDs: \\[{line.id}\\]"):
            self._load_migration().migrate(self.env.cr, "19.0.1.0.0")

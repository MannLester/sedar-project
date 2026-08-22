import importlib.util
from pathlib import Path

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
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
    def _create_employee_profile(cls, company, suffix):
        employee = cls.env["hr.employee"].with_company(company).create({
            "name": "Manpower %s Employee" % suffix,
            "company_id": company.id,
        })
        return cls.env["sedar.crew.profile"].create({
            "employee_id": employee.id,
            "employee_number": "MCP-%s" % suffix,
            "rank_id": cls.rank.id,
        })

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

    def test_manpower_request_company_is_locked_after_lines_exist(self):
        action = self.shortage_b.with_company(self.company_a).action_create_manpower_request()
        request = self.env["sedar.manpower.request"].browse(action["res_id"])
        department_a = self.env["hr.department"].create({
            "name": "Locked Manpower Company Department A",
            "company_id": self.company_a.id,
        })

        with self.assertRaisesRegex(ValidationError, "company cannot change"):
            request.write({
                "company_id": self.company_a.id,
                "department_id": department_a.id,
            })

        self.assertEqual(request.company_id, self.company_b)
        self.assertEqual(request.line_ids.shortage_ids, self.shortage_b)

    def test_shortage_and_manpower_ownership_chain_cannot_be_reparented(self):
        action = self.shortage_b.with_company(self.company_a).action_create_manpower_request()
        request_b = self.env["sedar.manpower.request"].browse(action["res_id"])
        line_b = request_b.line_ids
        shortage_action_b = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": self.shortage_b.id,
            "action_type": "manpower",
        })
        partner_a = self.env["res.partner"].create({
            "name": "Immutable Ownership Client A",
            "company_id": self.company_a.id,
        })
        shortage_a = self._create_shortage(self.company_a, partner_a)
        department_a = self.env["hr.department"].create({
            "name": "Immutable Ownership Department A",
            "company_id": self.company_a.id,
        })
        request_a = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Replacement parent for rejection checks.",
        })

        with self.assertRaisesRegex(ValidationError, "Tug Assignment cannot move"):
            self.shortage_b.requirement_id.tug_assignment_id.write({
                "order_id": shortage_a.order_id.id,
            })
        with self.assertRaisesRegex(ValidationError, "crew shortage cannot move"):
            self.shortage_b.write({"requirement_id": shortage_a.requirement_id.id})
        with self.assertRaisesRegex(ValidationError, "action cannot move"):
            shortage_action_b.write({"shortage_id": shortage_a.id})
        with self.assertRaisesRegex(ValidationError, "line cannot move"):
            line_b.write({"request_id": request_a.id})

        self.assertEqual(self.shortage_b.company_id, self.company_b)
        self.assertEqual(line_b.request_id, request_b)
        self.assertEqual(shortage_action_b.shortage_id, self.shortage_b)

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

    def test_company_checked_shortage_links_and_action_employee(self):
        partner_a = self.env["res.partner"].create({
            "name": "Company A Manpower Client",
            "company_id": self.company_a.id,
        })
        shortage_a = self._create_shortage(self.company_a, partner_a)
        profile_a = self._create_employee_profile(self.company_a, "CROSS-A")
        assignment_a = self.env["sedar.crew.assignment"].create({
            "requirement_id": shortage_a.requirement_id.id,
            "crew_profile_id": profile_a.id,
        })

        with self.assertRaises(UserError):
            self.shortage_b.write({"crew_assignment_id": assignment_a.id})

        department_a = self.env["hr.department"].create({
            "name": "Cross-company Link Department A",
            "company_id": self.company_a.id,
        })
        request_a = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Cross-company shortage link test.",
        })
        line_a = self.env["sedar.manpower.request.line"].create({
            "request_id": request_a.id,
            "crew_rank_id": self.rank.id,
            "required_date": fields.Date.today(),
        })
        with self.assertRaises(UserError):
            self.shortage_b.write({"manpower_request_line_id": line_a.id})

        action_b = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": self.shortage_b.id,
            "action_type": "manpower",
        })
        employee_a = profile_a.employee_id
        with self.assertRaises(UserError):
            action_b.write({"assigned_employee_id": employee_a.id})

    def test_manpower_line_accepts_shared_job_and_rejects_foreign_job(self):
        department_a = self.env["hr.department"].create({
            "name": "Marine Jobs A",
            "company_id": self.company_a.id,
        })
        request_a = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Job company compatibility test.",
        })
        foreign_job = self.env["hr.job"].create({
            "name": "Company B Job",
            "company_id": self.company_b.id,
        })
        with self.assertRaises(UserError):
            self.env["sedar.manpower.request.line"].create({
                "request_id": request_a.id,
                "crew_rank_id": self.rank.id,
                "required_date": fields.Date.today(),
                "job_id": foreign_job.id,
            })

        shared_job = self.env["hr.job"].create({
            "name": "Shared Marine Job",
            "company_id": False,
        })
        line = self.env["sedar.manpower.request.line"].create({
            "request_id": request_a.id,
            "crew_rank_id": self.rank.id,
            "required_date": fields.Date.today(),
            "job_id": shared_job.id,
        })
        self.assertEqual(line.job_id, shared_job)

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

    def test_upgrade_rejects_cross_company_shortage_links(self):
        partner_a = self.env["res.partner"].create({
            "name": "Company A Migration Client",
            "company_id": self.company_a.id,
        })
        shortage_a = self._create_shortage(self.company_a, partner_a)
        profile_a = self._create_employee_profile(self.company_a, "MIG-A")
        assignment_a = self.env["sedar.crew.assignment"].create({
            "requirement_id": shortage_a.requirement_id.id,
            "crew_profile_id": profile_a.id,
        })
        operation_a = self.env["sedar.marine.operation"].create({
            "order_id": shortage_a.order_id.id,
        })
        department_a = self.env["hr.department"].create({
            "name": "Migration Department A",
            "company_id": self.company_a.id,
        })
        request_a = self.env["sedar.manpower.request"].create({
            "company_id": self.company_a.id,
            "department_id": department_a.id,
            "business_justification": "Cross-company migration links.",
        })
        line_a = self.env["sedar.manpower.request.line"].create({
            "request_id": request_a.id,
            "crew_rank_id": self.rank.id,
            "required_date": fields.Date.today(),
        })
        migration = self._load_migration()
        checks = [
            ("crew_assignment_id", assignment_a.id, "crew assignments conflict"),
            ("operation_id", operation_a.id, "Marine Operations conflict"),
            ("manpower_request_line_id", line_a.id, "manpower lines conflict"),
        ]
        for column, value, message in checks:
            self.env.cr.execute(
                "UPDATE sedar_crew_shortage SET %s = %%s WHERE id = %%s" % column,
                (value, self.shortage_b.id),
            )
            with self.assertRaisesRegex(RuntimeError, message):
                migration._reject_legacy_link_conflicts(self.env.cr)
            self.env.cr.execute(
                "UPDATE sedar_crew_shortage SET %s = NULL WHERE id = %%s" % column,
                (self.shortage_b.id,),
            )

    def test_upgrade_rejects_cross_company_shortage_action_employee(self):
        action = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": self.shortage_b.id,
            "action_type": "manpower",
        })
        employee_a = self.env["hr.employee"].with_company(self.company_a).create({
            "name": "Legacy Cross Company Employee",
            "company_id": self.company_a.id,
        })
        self.env.cr.execute(
            "UPDATE sedar_crew_shortage_action SET assigned_employee_id = %s WHERE id = %s",
            (employee_a.id, action.id),
        )

        with self.assertRaisesRegex(RuntimeError, "actions have employees from another company"):
            self._load_migration()._reject_legacy_link_conflicts(self.env.cr)

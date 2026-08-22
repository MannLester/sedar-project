from datetime import datetime
import importlib.util
from pathlib import Path

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrewingAvailability(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Availability Client"})
        cls.port = cls.env["sedar.marine.port"].create({"name": "Availability Port", "code": "AVL"})
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Availability Assist",
            "code": "AVL-A",
            "pricing_basis": "per_service",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Availability Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Availability Tug",
            "registration_number": "AVL-TUG",
            "tug_class_id": cls.tug_class.id,
            "availability_status": "available",
        })
        cls.rank = cls.env["sedar.crew.rank"].create({"name": "Availability Master", "code": "AVL-MASTER"})
        cls.certificate_type = cls.env["sedar.crew.certificate.type"].create({
            "name": "Availability STCW",
            "code": "AVL-STCW",
        })
        cls.primary_profile = cls._create_profile("Primary")
        cls.relief_profile = cls._create_profile("Relief")

    @classmethod
    def _create_profile(cls, suffix):
        employee = cls.env["hr.employee"].create({"name": "Availability %s Crew" % suffix})
        profile = cls.env["sedar.crew.profile"].create({
            "employee_id": employee.id,
            "employee_number": "AVL-%s" % suffix.upper(),
            "rank_id": cls.rank.id,
            "home_tugboat_id": cls.tug.id,
            "availability_status": "available",
        })
        cls.env["sedar.crew.certificate"].create({
            "crew_profile_id": profile.id,
            "certificate_type_id": cls.certificate_type.id,
            "certificate_number": "AVL-CERT-%s" % suffix.upper(),
            "issue_date": "2026-01-01",
            "expiry_date": "2027-01-01",
        })
        return profile

    def _make_requirement(self):
        order = self.env["sedar.marine.service.order"].create({
            "client_id": self.partner.id,
            "assisted_vessel_name": "MV Availability",
            "service_type_id": self.service.id,
            "number_of_tugs": 1,
            "scope_of_work": "Availability test.",
            "port_id": self.port.id,
            "requested_start": datetime(2026, 9, 1, 8, 0, 0),
            "estimated_duration_hours": 2,
            "state": "planning",
        })
        tug_assignment = self.env["sedar.tug.assignment"].create({
            "order_id": order.id,
            "tugboat_id": self.tug.id,
        })
        requirement = self.env["sedar.manning.requirement"].create({
            "tug_assignment_id": tug_assignment.id,
            "rank_id": self.rank.id,
            "required_count": 1,
            "required_certificate_type_ids": [(6, 0, [self.certificate_type.id])],
        })
        return order, requirement

    def test_dated_unavailability_blocks_only_overlapping_assignment(self):
        _order, requirement = self._make_requirement()
        assignment = self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement.id,
            "crew_profile_id": self.primary_profile.id,
        })
        self.assertTrue(assignment.is_eligible)

        self.env["sedar.crew.unavailability"].create({
            "crew_profile_id": self.primary_profile.id,
            "source": "leave",
            "date_start": datetime(2026, 9, 1, 7, 0, 0),
            "date_end": datetime(2026, 9, 1, 12, 0, 0),
            "reason": "Approved family leave",
            "state": "active",
        })
        assignment.invalidate_recordset()
        self.assertFalse(assignment.is_eligible)
        self.assertIn("Dated unavailability", assignment.eligibility_reason)

    def test_temporary_relief_creates_assignment_and_resolves_shortage(self):
        _order, requirement = self._make_requirement()
        shortage = self.env["sedar.crew.shortage"].create({
            "requirement_id": requirement.id,
            "missing_count": 1,
            "reason": "leave",
            "root_cause": "leave",
            "resolution_action": "temporary_reliever",
            "review_state": "action_required",
        })
        action = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": shortage.id,
            "action_type": "temporary_reliever",
            "relief_crew_profile_id": self.relief_profile.id,
            "planned_date": fields.Date.to_date(requirement.tug_assignment_id.order_id.requested_start),
            "outcome": "Relief crew assigned for the service window.",
        })

        action.action_complete()

        self.assertEqual(action.state, "completed")
        self.assertTrue(action.relief_assignment_id)
        self.assertTrue(action.relief_assignment_id.is_eligible)
        self.assertEqual(shortage.status, "resolved")
        self.assertEqual(shortage.review_state, "resolved")

    def _make_other_company_assignment(self):
        other_company = self.env["res.company"].create({
            "name": "Other Crewing Availability Company",
        })
        order = self.env["sedar.marine.service.order"].with_company(other_company).create({
            "company_id": other_company.id,
            "client_id": self.partner.id,
            "assisted_vessel_name": "MV Other Availability",
            "service_type_id": self.service.id,
            "scope_of_work": "Cross-company relief assignment test.",
            "port_id": self.port.id,
            "requested_start": datetime(2026, 9, 2, 8, 0, 0),
        })
        tug_assignment = self.env["sedar.tug.assignment"].create({
            "order_id": order.id,
            "tugboat_id": self.tug.id,
        })
        requirement = self.env["sedar.manning.requirement"].create({
            "tug_assignment_id": tug_assignment.id,
            "rank_id": self.rank.id,
        })
        return self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement.id,
            "crew_profile_id": self.relief_profile.id,
        })

    def test_relief_assignment_rejects_another_company(self):
        _order, requirement = self._make_requirement()
        shortage = self.env["sedar.crew.shortage"].create({
            "requirement_id": requirement.id,
            "reason": "leave",
        })
        action = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": shortage.id,
            "action_type": "temporary_reliever",
        })
        foreign_assignment = self._make_other_company_assignment()

        with self.assertRaises(UserError):
            action.write({"relief_assignment_id": foreign_assignment.id})

    def test_upgrade_rejects_cross_company_relief_assignment(self):
        _order, requirement = self._make_requirement()
        shortage = self.env["sedar.crew.shortage"].create({
            "requirement_id": requirement.id,
            "reason": "leave",
        })
        action = self.env["sedar.crew.shortage.action"].create({
            "shortage_id": shortage.id,
            "action_type": "temporary_reliever",
        })
        foreign_assignment = self._make_other_company_assignment()
        self.env.cr.execute(
            "UPDATE sedar_crew_shortage_action SET relief_assignment_id = %s WHERE id = %s",
            (foreign_assignment.id, action.id),
        )
        migration_path = (
            Path(__file__).parents[1]
            / "migrations/19.0.2.0.0/pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "sedar_crewing_availability_pre_migrate", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        with self.assertRaisesRegex(RuntimeError, f"action IDs: \\[{action.id}\\]"):
            migration.migrate(self.env.cr, "19.0.1.0.0")

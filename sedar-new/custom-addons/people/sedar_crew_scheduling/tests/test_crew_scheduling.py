from datetime import datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrewScheduling(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Scheduling Client"})
        cls.port = cls.env["sedar.marine.port"].create({"name": "Scheduling Port", "code": "SCH"})
        cls.service = cls.env["sedar.marine.service.type"].create({
            "name": "Scheduling Assist",
            "code": "SCH-A",
            "pricing_basis": "per_service",
        })
        cls.tug_class = cls.env["sedar.tug.class"].create({"name": "Scheduling Tug Class"})
        cls.tug = cls.env["sedar.tugboat"].create({
            "name": "Scheduling Tug",
            "registration_number": "SCH-TUG",
            "tug_class_id": cls.tug_class.id,
            "availability_status": "available",
        })
        cls.rank = cls.env["sedar.crew.rank"].create({"name": "Scheduling Master", "code": "SCH-MASTER"})
        cls.certificate_type = cls.env["sedar.crew.certificate.type"].create({
            "name": "Scheduling STCW",
            "code": "SCH-STCW",
        })
        cls.primary_profile = cls._create_profile("Primary", "2027-01-01")
        cls.relief_profile = cls._create_profile("Relief", "2027-01-01")
        cls.expired_profile = cls._create_profile("Expired", "2026-01-01")

    @classmethod
    def _create_profile(cls, suffix, expiry_date):
        employee = cls.env["hr.employee"].create({"name": "Scheduling %s Crew" % suffix})
        profile = cls.env["sedar.crew.profile"].create({
            "employee_id": employee.id,
            "employee_number": "SCH-%s" % suffix.upper(),
            "rank_id": cls.rank.id,
            "home_tugboat_id": cls.tug.id,
            "availability_status": "available",
        })
        cls.env["sedar.crew.certificate"].create({
            "crew_profile_id": profile.id,
            "certificate_type_id": cls.certificate_type.id,
            "certificate_number": "SCH-CERT-%s" % suffix.upper(),
            "issue_date": "2026-01-01",
            "expiry_date": expiry_date,
        })
        return profile

    def _make_requirement(self, name_suffix):
        order = self.env["sedar.marine.service.order"].create({
            "client_id": self.partner.id,
            "assisted_vessel_name": "MV Scheduling %s" % name_suffix,
            "service_type_id": self.service.id,
            "number_of_tugs": 1,
            "scope_of_work": "Scheduling test.",
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

    def test_confirm_assignment_rejects_overlapping_schedule(self):
        _order_one, requirement_one = self._make_requirement("One")
        assignment_one = self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement_one.id,
            "crew_profile_id": self.primary_profile.id,
        })
        assignment_one.action_confirm_assignment()
        self.assertEqual(assignment_one.state, "confirmed")

        _order_two, requirement_two = self._make_requirement("Two")
        assignment_two = self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement_two.id,
            "crew_profile_id": self.primary_profile.id,
        })
        self.assertFalse(assignment_two.is_eligible)
        self.assertIn("Overlapping crew assignment", assignment_two.eligibility_reason)
        with self.assertRaises(UserError):
            assignment_two.action_confirm_assignment()

        assignment_two.action_reject_assignment()
        self.assertEqual(assignment_two.scheduling_status, "rejected")

    def test_replacement_candidates_respect_availability_and_credentials(self):
        _order, requirement = self._make_requirement("Candidates")
        assignment = self.env["sedar.crew.assignment"].create({
            "requirement_id": requirement.id,
            "crew_profile_id": self.primary_profile.id,
        })
        self.env["sedar.crew.unavailability"].create({
            "crew_profile_id": self.primary_profile.id,
            "source": "leave",
            "date_start": datetime(2026, 9, 1, 7, 0, 0),
            "date_end": datetime(2026, 9, 1, 12, 0, 0),
            "reason": "Approved leave",
            "state": "active",
        })
        assignment.invalidate_recordset()

        self.assertFalse(assignment.is_eligible)
        self.assertIn(self.relief_profile, assignment.replacement_candidate_ids)
        self.assertNotIn(self.expired_profile, assignment.replacement_candidate_ids)

    def test_overlapping_active_rotations_are_rejected(self):
        rotation = self.env["sedar.crew.rotation"].create({
            "crew_profile_id": self.primary_profile.id,
            "tugboat_id": self.tug.id,
            "date_start": datetime(2026, 9, 1, 0, 0, 0),
            "date_end": datetime(2026, 9, 15, 0, 0, 0),
            "state": "planned",
        })
        self.assertEqual(rotation.state, "planned")

        with self.assertRaises(ValidationError):
            self.env["sedar.crew.rotation"].create({
                "crew_profile_id": self.primary_profile.id,
                "tugboat_id": self.tug.id,
                "date_start": datetime(2026, 9, 10, 0, 0, 0),
                "date_end": datetime(2026, 9, 20, 0, 0, 0),
                "state": "planned",
            })


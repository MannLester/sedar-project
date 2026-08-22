import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "run_odoo_tests.py"
SPEC = importlib.util.spec_from_file_location("run_odoo_tests", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class TestRunnerSafety(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        database_exists = patch.object(runner, "database_exists", return_value=(0, False))
        database_exists.start()
        self.addCleanup(database_exists.stop)

    def test_generated_database_is_owned_safe_and_postgres_compatible(self):
        database = runner.generate_database_name()
        self.assertTrue(database.startswith("sedar_test_"))
        self.assertLessEqual(len(database), 63)
        self.assertEqual(database, database.lower())

    def test_shared_or_user_supplied_database_names_are_rejected(self):
        for database in ("sedar_demo", "postgres", "sedar_test_shared", "SEDAR_TEST_bad"):
            with self.subTest(database=database), self.assertRaises(runner.RunnerError):
                runner.validate_database_name(database)

    def test_module_and_tag_validation_rejects_injection_and_unselected_modules(self):
        with self.assertRaises(runner.RunnerError):
            runner.validate_modules(self.root, ["sedar_marine_finance; rm -rf x"])
        with self.assertRaises(runner.RunnerError):
            runner.validate_test_tags("/sedar_marketing", {"sedar_marine_finance"})
        for invalid in (
            "foo-bar/sedar_marine_finance",
            "foo+bar/sedar_marine_finance",
            "/sedar_marine_finance:Bad-Class",
            "+",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(runner.RunnerError):
                runner.validate_test_tags(invalid, {"sedar_marine_finance"})

    def test_supported_odoo_tag_selectors_are_preserved(self):
        selected = {"sedar_marine_finance"}
        for tags in (
            "standard,-slow",
            "-slow",
            "/sedar_marine_finance",
            "/sedar_marine_finance:TestMarineFinanceWorkflow",
            "/sedar_marine_finance:TestMarineFinanceWorkflow.test_missing_tariff_is_pricing_exception",
            ".test_missing_tariff_is_pricing_exception",
        ):
            with self.subTest(tags=tags):
                self.assertEqual(runner.validate_test_tags(tags, selected), tags)

    @patch.object(runner, "cleanup", return_value=[])
    @patch.object(runner, "command_result", side_effect=[0, 0, 0, 0])
    def test_success_creates_runs_and_cleans_owned_database(self, command_result, cleanup):
        self.assertEqual(runner.run(self.root, ["sedar_marine_finance"]), 0)
        cleanup.assert_called_once()
        self.assertRegex(cleanup.call_args.args[3], runner.OWNERSHIP_MARKER_RE)
        test_command = command_result.call_args_list[-1].args[0]
        self.assertEqual(test_command[:4], ["docker", "compose", "run", "--rm"])
        self.assertIn("--stop-after-init", test_command)
        self.assertNotIn("--no-http", test_command)
        label = test_command[test_command.index("--label") + 1]
        self.assertEqual(label, f"{runner.CONTAINER_OWNER_LABEL}={cleanup.call_args.args[3]}")
        database = cleanup.call_args.args[1]
        self.assertEqual(test_command[test_command.index("--database") + 1], database)
        self.assertEqual(test_command[test_command.index("--db-filter") + 1], f"^{database}$")
        self.assertEqual(test_command[test_command.index("--http-interface") + 1], "127.0.0.1")
        self.assertEqual(test_command[test_command.index("--data-dir") + 1], "/tmp/sedar-odoo-test-data")

    @patch.object(runner, "cleanup", return_value=[])
    @patch.object(runner, "command_result", side_effect=[0, 0, 7])
    def test_failed_creation_checks_the_database_ownership_marker(self, command_result, cleanup):
        self.assertEqual(runner.run(self.root, ["sedar_marine_finance"]), 7)
        self.assertRegex(cleanup.call_args.args[3], runner.OWNERSHIP_MARKER_RE)

    @patch.object(runner, "cleanup", return_value=[])
    @patch.object(runner, "command_result", side_effect=[0, 0, KeyboardInterrupt])
    def test_interrupted_creation_checks_the_database_ownership_marker(self, command_result, cleanup):
        with self.assertRaises(KeyboardInterrupt):
            runner.run(self.root, ["sedar_marine_finance"])
        self.assertRegex(cleanup.call_args.args[3], runner.OWNERSHIP_MARKER_RE)

    @patch.object(runner, "cleanup", return_value=[])
    @patch.object(runner, "command_result", side_effect=[0, 0])
    def test_preexisting_generated_name_is_never_claimed(self, command_result, cleanup):
        with patch.object(runner, "database_exists", return_value=(0, True)):
            with self.assertRaises(runner.RunnerError):
                runner.run(self.root, ["sedar_marine_finance"])
        self.assertRegex(cleanup.call_args.args[3], runner.OWNERSHIP_MARKER_RE)

    @patch.object(runner, "cleanup", return_value=[])
    @patch.object(runner, "command_result", side_effect=[0, 0, 0, 9])
    def test_test_failure_preserves_status_and_cleans(self, command_result, cleanup):
        self.assertEqual(runner.run(self.root, ["sedar_marine_finance"]), 9)
        self.assertRegex(cleanup.call_args.args[3], runner.OWNERSHIP_MARKER_RE)

    @patch.object(runner, "cleanup", return_value=[])
    @patch.object(runner, "command_result", side_effect=[0, 0, 0, KeyboardInterrupt])
    def test_interruption_still_cleans(self, command_result, cleanup):
        with self.assertRaises(KeyboardInterrupt):
            runner.run(self.root, ["sedar_marine_finance"])
        self.assertRegex(cleanup.call_args.args[3], runner.OWNERSHIP_MARKER_RE)

    @patch.object(runner, "cleanup", return_value=["Test database still exists: sedar_test_example."])
    @patch.object(runner, "command_result", side_effect=[0, 0, 0, KeyboardInterrupt])
    def test_cleanup_failure_does_not_hide_interruption(self, command_result, cleanup):
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            with self.assertRaises(KeyboardInterrupt):
                runner.run(self.root, ["sedar_marine_finance"])
        self.assertIn("Test database still exists", stderr.getvalue())

    @patch.object(runner, "cleanup", return_value=["Test database still exists: sedar_test_example."])
    @patch.object(runner, "command_result", side_effect=[0, 0, 0, 0])
    def test_cleanup_failure_turns_success_into_failure(self, command_result, cleanup):
        with self.assertRaises(runner.RunnerError):
            runner.run(self.root, ["sedar_marine_finance"])

    @patch.object(runner, "cleanup", return_value=["Test database still exists: sedar_test_example."])
    @patch.object(runner, "command_result", side_effect=[0, 0, 0, 9])
    def test_cleanup_failure_is_reported_without_hiding_test_failure(self, command_result, cleanup):
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(runner.run(self.root, ["sedar_marine_finance"]), 9)
        self.assertIn("Test database still exists", stderr.getvalue())

    @patch.object(runner, "database_exists", return_value=(0, False))
    @patch.object(runner, "database_has_marker", return_value=(0, True))
    @patch.object(runner, "command_output", return_value=(0, ""))
    @patch.object(runner, "command_result", return_value=0)
    def test_cleanup_verifies_database_absence(
        self, command_result, command_output, database_has_marker, database_exists
    ):
        errors = runner.cleanup(
            self.root, "sedar_test_123456789abc", "sedar-odoo-test-123456789abc",
            "sedar_runner_123456789abcdef0123456789abcdef0",
            True,
        )
        self.assertEqual(errors, [])
        database_exists.assert_called_once_with(self.root, "sedar_test_123456789abc")

    @patch.object(runner, "database_exists", return_value=(0, True))
    @patch.object(runner, "database_has_marker", return_value=(0, True))
    @patch.object(runner, "command_output", return_value=(0, ""))
    @patch.object(runner, "command_result", return_value=0)
    def test_cleanup_reports_database_that_still_exists(
        self, command_result, command_output, database_has_marker, database_exists
    ):
        database = "sedar_test_123456789abc"
        errors = runner.cleanup(
            self.root, database, "sedar-odoo-test-123456789abc",
            "sedar_runner_123456789abcdef0123456789abcdef0",
            True,
        )
        self.assertTrue(any(database in error for error in errors))

    @patch.object(runner, "database_has_marker", return_value=(0, False))
    @patch.object(runner, "command_output", return_value=(0, ""))
    @patch.object(runner, "command_result")
    def test_cleanup_never_drops_database_without_its_marker(
        self, command_result, command_output, database_has_marker
    ):
        errors = runner.cleanup(
            self.root, "sedar_test_123456789abc", "sedar-odoo-test-123456789abc",
            "sedar_runner_123456789abcdef0123456789abcdef0",
            True,
        )
        self.assertEqual(errors, [])
        command_result.assert_not_called()

    @patch.object(runner, "database_exists", return_value=(0, False))
    @patch.object(runner, "database_has_marker", return_value=(0, True))
    @patch.object(runner, "_container_marker", return_value=(0, "sedar_runner_123456789abcdef0123456789abcdef0"))
    @patch.object(runner, "_container_names", side_effect=[
        (0, {"sedar-odoo-test-123456789abc"}), (0, set()),
    ])
    @patch.object(runner, "command_result", side_effect=[0, 0])
    def test_cleanup_removes_and_verifies_owned_container(
        self, command_result, container_names, container_marker,
        database_has_marker, database_exists
    ):
        errors = runner.cleanup(
            self.root, "sedar_test_123456789abc", "sedar-odoo-test-123456789abc",
            "sedar_runner_123456789abcdef0123456789abcdef0",
            True,
        )
        self.assertEqual(errors, [])
        self.assertEqual(command_result.call_args_list[0].args[0][:3], ["docker", "rm", "--force"])

    @patch.object(runner, "database_exists", return_value=(0, True))
    @patch.object(runner, "database_has_marker", return_value=(0, False))
    @patch.object(runner, "_container_names", return_value=(0, set()))
    @patch.object(runner, "command_result")
    def test_cleanup_reports_unmarked_database_left_by_interrupted_creation(
        self, command_result, container_names, database_has_marker, database_exists
    ):
        database = "sedar_test_123456789abc"
        errors = runner.cleanup(
            self.root, database, "sedar-odoo-test-123456789abc",
            "sedar_runner_123456789abcdef0123456789abcdef0", True,
        )
        self.assertTrue(any("Retained unowned test database" in error for error in errors))
        command_result.assert_not_called()

    @patch.object(runner, "database_exists", return_value=(0, False))
    @patch.object(runner, "database_has_marker", return_value=(0, False))
    @patch.object(runner, "_container_marker", return_value=(0, "another-owner"))
    @patch.object(runner, "_container_names", return_value=(0, {"sedar-odoo-test-123456789abc"}))
    @patch.object(runner, "command_result")
    def test_cleanup_retains_same_name_container_with_wrong_marker(
        self, command_result, container_names, container_marker,
        database_has_marker, database_exists
    ):
        errors = runner.cleanup(
            self.root, "sedar_test_123456789abc", "sedar-odoo-test-123456789abc",
            "sedar_runner_123456789abcdef0123456789abcdef0", True,
        )
        self.assertTrue(any("Retained unowned test container" in error for error in errors))
        command_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()

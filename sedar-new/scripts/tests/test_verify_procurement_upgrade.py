import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "verify_procurement_upgrade.py"
SPEC = importlib.util.spec_from_file_location("verify_procurement_upgrade", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)


class TestProcurementUpgradeVerifier(unittest.TestCase):
    def test_base_ref_validation_rejects_revision_syntax_and_shell_input(self):
        self.assertEqual(verifier.validate_ref(verifier.DEFAULT_BASE), verifier.DEFAULT_BASE)
        for unsafe in ("HEAD..main", "HEAD^{tree}", "main;rm", "", "../main"):
            with self.subTest(unsafe=unsafe), self.assertRaises(verifier.VerificationError):
                verifier.validate_ref(unsafe)

    def test_compose_modules_uses_exact_declared_order(self):
        with tempfile.TemporaryDirectory() as temp:
            compose = Path(temp) / "docker-compose.yml"
            compose.write_text('command: |\n  SEDAR_MODULES="module_a,module_b,module_c"\n')
            self.assertEqual(
                verifier.compose_modules(compose),
                ["module_a", "module_b", "module_c"],
            )

    def test_compose_modules_rejects_missing_declaration(self):
        with tempfile.TemporaryDirectory() as temp:
            compose = Path(temp) / "docker-compose.yml"
            compose.write_text("services: {}\n")
            with self.assertRaises(verifier.VerificationError):
                verifier.compose_modules(compose)

    def test_compose_commands_ignore_ambient_selector_variables(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = verifier.VerificationRun(
                source_root=root,
                base_ref=verifier.DEFAULT_BASE,
                keep_success=True,
                run_root=root / "run",
                workspace=root / "workspace",
                project="sedar_release_test",
            )
            expected_file = str(run.compose_root / "docker-compose.yml")
            with patch.dict(
                os.environ,
                {
                    "COMPOSE_FILE": "/tmp/hostile-compose.yml",
                    "COMPOSE_PROJECT_NAME": "shared-production",
                    "COMPOSE_PROFILES": "hostile",
                },
            ):
                command = verifier.compose_command(run, "config", "--quiet")
                environment = verifier.compose_environment()

            self.assertEqual(command[2:8], [
                "--file", expected_file,
                "--project-directory", str(run.compose_root),
                "--project-name", run.project,
            ])
            self.assertFalse(any(
                key.startswith("COMPOSE_") for key in environment
            ))

    def test_legacy_comparison_accepts_new_records_and_fields(self):
        before = [{"key": "purchase.order:4", "values": {"state": "purchase", "line_ids": [8]}}]
        after = [
            {"key": "purchase.order:4", "values": {"state": "purchase", "line_ids": [8], "new_field": 1}},
            {"key": "purchase.order:9", "values": {"state": "draft"}},
        ]
        verifier.compare_legacy(before, after)

    def test_legacy_comparison_rejects_missing_or_changed_facts(self):
        before = [{"key": "stock.move:3", "values": {"state": "done", "quantity": 2.0}}]
        with self.assertRaises(verifier.VerificationError):
            verifier.compare_legacy(before, [])
        with self.assertRaises(verifier.VerificationError):
            verifier.compare_legacy(
                before,
                [{"key": "stock.move:3", "values": {"state": "done", "quantity": 3.0}}],
            )

    def test_pm_scenario_rejects_missing_stable_fixture_records(self):
        with self.assertRaises(verifier.VerificationError):
            verifier.assert_pm_scenario([])

    def test_candidate_tree_digest_includes_uncommitted_source_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            source = root / "source.py"
            source.write_text("value = 1\n")
            first = verifier.candidate_tree_digest(root)
            source.write_text("value = 2\n")
            second = verifier.candidate_tree_digest(root)
            self.assertNotEqual(first, second)

    def test_candidate_metadata_is_captured_in_command_evidence(self):
        with tempfile.TemporaryDirectory() as source_temp, tempfile.TemporaryDirectory() as run_temp:
            source_root = Path(source_temp)
            run_root = Path(run_temp)
            subprocess.run(["git", "init", "--quiet"], cwd=source_root, check=True)
            source = source_root / "source.py"
            source.write_text("value = 1\n")
            subprocess.run(["git", "add", "source.py"], cwd=source_root, check=True)
            subprocess.run(
                [
                    "git", "-c", "user.name=Verifier Test",
                    "-c", "user.email=verifier@test.example",
                    "commit", "--quiet", "-m", "fixture",
                ],
                cwd=source_root,
                check=True,
            )
            source.write_text("value = 2\n")
            (run_root / "logs").mkdir()
            run = verifier.VerificationRun(
                source_root=source_root,
                base_ref="HEAD",
                keep_success=True,
                run_root=run_root,
                workspace=run_root / "workspace",
                project="sedar_release_test",
            )

            verifier.capture_candidate_metadata(run)

            self.assertTrue(run.candidate_dirty)
            self.assertEqual(len(run.candidate_sha), 40)
            self.assertEqual(len(run.candidate_tree_sha256), 64)
            self.assertEqual(
                [command["name"] for command in run.commands],
                [
                    "git-status-candidate",
                    "git-rev-parse-candidate",
                    "list-candidate-files",
                ],
            )
            self.assertTrue(all(command["exit_code"] == 0 for command in run.commands))

    def test_cleanup_rejects_workspace_outside_run_root(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            run = verifier.VerificationRun(
                source_root=Path(first),
                base_ref=verifier.DEFAULT_BASE,
                keep_success=False,
                run_root=Path(first),
                workspace=Path(second),
                project="sedar_release_test",
            )
            with self.assertRaises(verifier.VerificationError):
                verifier.cleanup(run)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

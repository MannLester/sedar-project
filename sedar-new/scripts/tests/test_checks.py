import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import check
from checks import boundaries, core, docs_sync, hygiene

MANIFEST = (
    "{{'name': '{name}', 'version': '19.0.1.0.0', 'depends': {depends}, "
    "'license': 'LGPL-3', 'installable': True, 'data': {data}}}"
)
BOUNDARIES = """
[domains]
marine = ["sedar_a", "sedar_b"]
demo = ["sedar_demo"]

[public_models]
sedar_a = ["sedar.a.public"]
"""
MODEL_A = """
from odoo import models


class A(models.Model):
    _name = "sedar.a.public"

    def _hidden(self):
        return 1

    def api(self):
        return 2


class AInternal(models.Model):
    _name = "sedar.a.internal"
"""


class Workspace:
    def __init__(self, boundaries_toml: str = BOUNDARIES):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "custom-addons").mkdir()
        (self.root / "architecture").mkdir()
        (self.root / "architecture" / "boundaries.toml").write_text(boundaries_toml)
        self.patches = [
            patch.object(core, "PROJECT_ROOT", self.root),
            patch.object(core, "ADDONS_ROOT", self.root / "custom-addons"),
            patch.object(core, "BOUNDARIES_FILE", self.root / "architecture" / "boundaries.toml"),
            patch.object(core, "MODELS_DOC", self.root / "models.md"),
        ]
        self.addon("sedar_demo", ["base"])

    def __enter__(self):
        for active in self.patches:
            active.start()
        return self

    def __exit__(self, *exc):
        for active in self.patches:
            active.stop()
        self.directory.cleanup()

    def addon(self, name: str, depends: list[str], files: dict[str, str] | None = None, data: list[str] | None = None):
        path = self.root / "custom-addons" / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "__manifest__.py").write_text(MANIFEST.format(name=name, depends=depends, data=data or []))
        for relative_path, content in (files or {}).items():
            target = path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(content))
        return path


class TestBoundaries(unittest.TestCase):
    def keys(self):
        return {violation.key for violation in boundaries.run()}

    def test_reaching_an_undeclared_model_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            ws.addon("sedar_b", ["sedar_a"], {"models/b.py": "def f(self):\n    return self.env['sedar.a.internal']\n"})
            self.assertIn("undeclared-model:sedar_b:sedar.a.internal", self.keys())

    def test_reaching_a_declared_model_is_allowed(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            ws.addon("sedar_b", ["sedar_a"], {"models/b.py": "def f(self):\n    return self.env['sedar.a.public']\n"})
            self.assertEqual(self.keys(), set())

    def test_using_a_model_without_depending_on_its_addon_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            ws.addon("sedar_b", ["base"], {"models/b.py": "def f(self):\n    return self.env['sedar.a.public']\n"})
            self.assertIn("missing-dependency:sedar_b:sedar.a.public", self.keys())

    def test_importing_an_addon_without_depending_on_it_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            ws.addon("sedar_b", ["base"], {"hooks.py": "from odoo.addons.sedar_a.hooks import x\n"})
            self.assertIn("missing-dependency:sedar_b:import:sedar_a", self.keys())

    def test_calling_a_private_method_of_a_dependency_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            ws.addon("sedar_b", ["sedar_a"], {"models/b.py": "def run(order):\n    order._hidden()\n"})
            self.assertIn("private-call:custom-addons/sedar_b/models/b.py:run:_hidden", self.keys())

    def test_calling_own_private_method_is_allowed(self):
        body = "class B:\n    def _own(self):\n        pass\n\n    def run(self):\n        self._own()\n"
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            ws.addon("sedar_b", ["sedar_a"], {"models/b.py": body})
            self.assertEqual(self.keys(), set())

    def test_production_addon_depending_on_demo_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["sedar_demo"])
            ws.addon("sedar_b", ["base"])
            ws.addon("sedar_demo", ["base"])
            self.assertIn("demo-dependency:sedar_a->sedar_demo", self.keys())

    def test_unassigned_addon_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"])
            ws.addon("sedar_b", ["base"])
            ws.addon("sedar_orphan", ["base"])
            self.assertIn("domain-missing:sedar_orphan", self.keys())


class TestHygiene(unittest.TestCase):
    def test_comments_are_rejected_but_pragmas_and_strings_are_allowed(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": "x = '# not a comment'\ny = 1  # explains y\nz = 2  # noqa: E501\n"})
            keys = {violation.key for violation in hygiene.check_comments()}
            self.assertEqual(keys, {"custom-addons/sedar_a/models/a.py:2"})

    def test_xml_comments_are_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"views/v.xml": "<odoo><!-- note --></odoo>\n"})
            self.assertEqual(len(hygiene.check_comments()), 1)

    def test_noqa_pragmas_are_counted_per_file(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": "a = 1  # noqa: E501\nb = 2  # noqa: E701\n"})
            keys = {violation.key for violation in hygiene.check_pragmas()}
            self.assertEqual(keys, {"custom-addons/sedar_a/models/a.py:noqa:2"})

    def test_oversized_python_file_is_rejected(self):
        with Workspace("[limits]\npython_lines = 3\n[domains]\n") as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": "a = 1\nb = 2\nc = 3\nd = 4\n"})
            keys = {violation.key for violation in hygiene.check_sizes()}
            self.assertEqual(keys, {"custom-addons/sedar_a/models/a.py"})

    def test_malformed_xml_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"views/v.xml": "<odoo><record></odoo>"})
            self.assertEqual(len(hygiene.check_xml()), 1)

    def test_data_file_missing_from_manifest_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"views/v.xml": "<odoo/>"})
            keys = {violation.key for violation in hygiene.check_manifests()}
            self.assertEqual(keys, {"sedar_a:unlisted:views/v.xml"})

    def test_manifest_entry_without_file_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], data=["views/gone.xml"])
            keys = {violation.key for violation in hygiene.check_manifests()}
            self.assertEqual(keys, {"sedar_a:missing:views/gone.xml"})

    def test_model_without_access_row_is_rejected(self):
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A})
            keys = {violation.key for violation in hygiene.check_access()}
            self.assertEqual(keys, {"sedar_a:sedar.a.public", "sedar_a:sedar.a.internal"})

    def test_model_with_access_rows_is_accepted(self):
        rows = "id,name,model_id:id\naccess_a,a,model_sedar_a_public\naccess_i,i,model_sedar_a_internal\n"
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A, "security/ir.model.access.csv": rows})
            self.assertEqual(hygiene.check_access(), [])


class TestDocsSync(unittest.TestCase):
    def test_undocumented_model_and_inherited_field_are_rejected(self):
        partner = """
        from odoo import fields, models

        class Partner(models.Model):
            _inherit = "res.partner"
            sedar_flag = fields.Boolean()
        """
        with Workspace() as ws:
            ws.addon("sedar_a", ["base"], {"models/a.py": MODEL_A, "models/p.py": partner})
            (ws.root / "models.md").write_text("`sedar.a.public`")
            keys = {violation.key for violation in docs_sync.run()}
            self.assertEqual(keys, {"model:sedar.a.internal", "field:res.partner.sedar_flag"})


class TestBaseline(unittest.TestCase):
    def test_baselined_violations_pass_new_ones_fail_and_fixed_ones_are_stale(self):
        found = [core.Violation("x", "old", "m"), core.Violation("x", "new", "m")]
        new, stale = check.partition(found, {"old", "gone"})
        self.assertEqual([violation.key for violation in new], ["new"])
        self.assertEqual(stale, {"gone"})


if __name__ == "__main__":
    unittest.main()

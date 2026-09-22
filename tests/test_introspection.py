import unittest

from z0archy_core.graph import zid
from z0archy_core.introspection import inspect_repository


class FakeTreeSource:
    kind = "github"

    def __init__(self):
        self.files = {
            "README.md": "# Demo\n",
            "ARCHITECTURE.md": "# Architecture\n",
            "package.json": '{"name":"@demo/root","workspaces":["packages/*"],"dependencies":{"@demo/core":"workspace:*"}}',
            "packages/core/package.json": '{"name":"@demo/core","version":"1.2.3"}',
            "packages/ui/package.json": '{"name":"@demo/ui","dependencies":{"@demo/core":"workspace:*"}}',
            "schemas/event.schema.json": '{"type":"object"}',
            ".github/workflows/ci.yml": "name: ci\n",
            "tests/test_smoke.py": "def test_smoke(): pass\n",
            "src/main.ts": "export const x = 1;\n",
        }

    def resolve_ref(self, repo, ref):
        return "a" * 40

    def read_text(self, repo, ref, path):
        return self.files.get(path)

    def list_tree(self, repo, ref):
        return {
            "truncated": False,
            "entries": [
                {
                    "path": path,
                    "type": "blob",
                    "oid": str(index + 1).rjust(40, "0"),
                    "size": len(text.encode("utf-8")),
                    "mode": "100644",
                }
                for index, (path, text) in enumerate(sorted(self.files.items()))
            ],
        }


class IntrospectionTests(unittest.TestCase):
    def test_deep_tree_compiles_high_signal_structure(self):
        pack = inspect_repository(
            FakeTreeSource(),
            "demo/repo",
            "main",
            resolved_ref="a" * 40,
        )
        nodes = {node["id"]: node for node in pack["nodes"]}
        edges = pack["edges"]

        root_pkg = zid("package", "demo/repo:@demo/root")
        core_pkg = zid("package", "demo/repo:@demo/core")
        ui_pkg = zid("package", "demo/repo:@demo/ui")
        self.assertIn(root_pkg, nodes)
        self.assertIn(core_pkg, nodes)
        self.assertIn(ui_pkg, nodes)

        dependency_pairs = {
            (edge["source"], edge["target"])
            for edge in edges
            if edge["type"] == "package_depends_on"
        }
        self.assertIn((root_pkg, core_pkg), dependency_pairs)
        self.assertIn((ui_pkg, core_pkg), dependency_pairs)

        artifacts = [
            node for node in nodes.values()
            if node["type"] == "source_artifact"
        ]
        roles = {node["attributes"]["role"] for node in artifacts}
        self.assertIn("schema", roles)
        self.assertIn("workflow", roles)

        test_surface = next(node for node in nodes.values() if node["type"] == "test_surface")
        self.assertEqual(test_surface["attributes"]["fileCount"], 1)

        structure = next(node for node in nodes.values() if node["type"] == "repo_structure")
        attrs = structure["attributes"]
        self.assertEqual(attrs["fileCount"], len(FakeTreeSource().files))
        self.assertEqual(attrs["packageCount"], 3)
        self.assertEqual(attrs["schemaCount"], 1)
        self.assertEqual(attrs["workflowCount"], 1)
        self.assertEqual(attrs["testFileCount"], 1)
        self.assertGreater(attrs["semanticCompressionRatio"], 0)

        summary = pack["summary"]["tree"]
        self.assertTrue(summary["available"])
        self.assertEqual(summary["packageCount"], 3)

    def test_tree_failure_falls_back_to_root_evidence(self):
        class FailingTreeSource(FakeTreeSource):
            def list_tree(self, repo, ref):
                raise RuntimeError("tree unavailable")

        pack = inspect_repository(
            FailingTreeSource(),
            "demo/repo",
            "main",
            resolved_ref="b" * 40,
        )
        readme = [
            node for node in pack["nodes"]
            if node["type"] == "source_artifact"
            and node["attributes"]["path"] == "README.md"
        ]
        self.assertEqual(len(readme), 1)
        self.assertIn("tree unavailable", pack["summary"]["tree"]["error"])


if __name__ == "__main__":
    unittest.main()

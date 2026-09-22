import unittest

from z0archy_core.graph import compile_graph, zid
from z0archy_core.lint import lint_graph
from z0archy_core.virtual import compile_virtual_snapshot, diff_graphs


class FakeSource:
    kind = "github"

    def __init__(self, files_by_ref):
        self.files_by_ref = files_by_ref

    def resolve_ref(self, repo, ref):
        return f"sha-{ref}"

    def read_text(self, repo, ref, path):
        logical_ref = ref.removeprefix("sha-")
        return self.files_by_ref.get(logical_ref, {}).get(path)


class VirtualSnapshotTests(unittest.TestCase):
    def base_graph(self):
        return compile_graph(
            {"components": {
                "a": {
                    "name": "A",
                    "repo": "o/a",
                    "kind": "runtime",
                    "depends_on": [],
                    "integrates_with": [],
                    "provides": [],
                    "consumes": [],
                }
            }},
            {"interfaces": {}},
            {"profiles": {}},
            {},
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_selected_ref_becomes_implemented_subgraph(self):
        provider = FakeSource({
            "main": {
                "README.md": "# A\n",
                "package.json": '{"name":"pkg-a","version":"1.0.0"}',
            }
        })
        graph = compile_virtual_snapshot(
            self.base_graph(),
            {"version": 1, "repos": {"o/a": {"source": "github", "ref": "main"}}},
            {"github": provider},
            generated_at="2026-01-01T00:00:01Z",
        )
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(zid("repo-ref", "o/a@sha-main"), ids)
        self.assertIn(zid("package", "o/a:pkg-a"), ids)
        implemented = [n for n in graph["nodes"] if n["type"] == "source_artifact"]
        self.assertTrue(implemented)
        self.assertTrue(all(n["provenance"][0]["class"] == "implemented" for n in implemented))

    def two_repo_graph(self, *, declared_integration=False):
        return compile_graph(
            {"components": {
                "a": {
                    "name": "A",
                    "repo": "o/a",
                    "kind": "runtime",
                    "depends_on": [],
                    "integrates_with": ["b"] if declared_integration else [],
                    "provides": [],
                    "consumes": [],
                },
                "b": {
                    "name": "B",
                    "repo": "o/b",
                    "kind": "measurement",
                    "depends_on": [],
                    "integrates_with": ["a"] if declared_integration else [],
                    "provides": [],
                    "consumes": [],
                },
            }},
            {"interfaces": {}},
            {"profiles": {}},
            {},
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_cross_repo_package_dependency_becomes_derived_drift_evidence(self):
        provider = FakeSource({
            "a-main": {
                "package.json": '{"name":"pkg-a","dependencies":{"pkg-b":"^1"}}',
            },
            "b-main": {
                "package.json": '{"name":"pkg-b","version":"1.0.0"}',
            },
        })
        graph = compile_virtual_snapshot(
            self.two_repo_graph(declared_integration=False),
            {
                "version": 1,
                "repos": {
                    "o/a": {"source": "github", "ref": "a-main"},
                    "o/b": {"source": "github", "ref": "b-main"},
                },
            },
            {"github": provider},
            generated_at="2026-01-01T00:00:01Z",
        )
        derived = [
            edge for edge in graph["edges"]
            if edge["type"] == "package_depends_on"
            and (edge.get("attributes") or {}).get("derivedCrossRepo")
        ]
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0]["attributes"]["sourceRepo"], "o/a")
        self.assertEqual(derived[0]["attributes"]["targetRepo"], "o/b")
        self.assertEqual(derived[0]["provenance"][0]["class"], "derived")
        codes = {row["code"] for row in lint_graph(graph)}
        self.assertIn("drift.cross_repo_package_dependency_undeclared", codes)

    def test_declared_integration_covers_cross_repo_package_dependency(self):
        provider = FakeSource({
            "a-main": {
                "package.json": '{"name":"pkg-a","dependencies":{"pkg-b":"^1"}}',
            },
            "b-main": {
                "package.json": '{"name":"pkg-b","version":"1.0.0"}',
            },
        })
        graph = compile_virtual_snapshot(
            self.two_repo_graph(declared_integration=True),
            {
                "version": 1,
                "repos": {
                    "o/a": {"source": "github", "ref": "a-main"},
                    "o/b": {"source": "github", "ref": "b-main"},
                },
            },
            {"github": provider},
            generated_at="2026-01-01T00:00:01Z",
        )
        codes = {row["code"] for row in lint_graph(graph)}
        self.assertNotIn("drift.cross_repo_package_dependency_undeclared", codes)

    def test_ref_change_has_structural_diff(self):
        provider = FakeSource({
            "main": {"README.md": "# main\n"},
            "feature": {"README.md": "# feature\n", "ARCHITECTURE.md": "# architecture\n"},
        })
        base = self.base_graph()
        main = compile_virtual_snapshot(
            base,
            {"version": 1, "repos": {"o/a": {"source": "github", "ref": "main"}}},
            {"github": provider},
            generated_at="2026-01-01T00:00:01Z",
        )
        feature = compile_virtual_snapshot(
            base,
            {"version": 1, "repos": {"o/a": {"source": "github", "ref": "feature"}}},
            {"github": provider},
            generated_at="2026-01-01T00:00:02Z",
        )
        diff = diff_graphs(main, feature)
        self.assertGreater(len(diff["nodes"]["added"]), 0)
        self.assertGreater(len(diff["nodes"]["removed"]), 0)


if __name__ == "__main__":
    unittest.main()

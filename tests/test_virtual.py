import unittest

from z0archy_core.graph import compile_graph, zid
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

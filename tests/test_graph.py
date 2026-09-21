import unittest

from z0archy_core.graph import compile_graph, zid


class GraphTests(unittest.TestCase):
    def test_declared_graph_contains_components_repos_interfaces_and_profiles(self):
        graph = compile_graph(
            {"components": {
                "a": {"name": "A", "repo": "o/a", "kind": "runtime", "depends_on": ["b"], "integrates_with": ["b"], "provides": ["evt.v1"], "consumes": []},
                "b": {"name": "B", "repo": "o/b", "kind": "measurement", "depends_on": [], "integrates_with": ["a"], "provides": [], "consumes": ["evt.v1"]},
            }},
            {"interfaces": {"evt.v1": {"owner": "a", "summary": "event"}}},
            {"profiles": {"core": {"components": ["a", "b"]}}},
            {"status": {"experimental": "x"}},
            generated_at="2026-01-01T00:00:00Z",
        )
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(zid("component", "a"), ids)
        self.assertIn(zid("repo", "o/a"), ids)
        self.assertIn(zid("interface", "evt.v1"), ids)
        self.assertIn(zid("profile", "core"), ids)
        self.assertTrue(all(n["provenance"][0]["class"] == "declared" for n in graph["nodes"]))
        kinds = [e["type"] for e in graph["edges"]]
        self.assertEqual(kinds.count("integrates_with"), 1)
        self.assertIn("depends_on", kinds)
        self.assertIn("provides", kinds)
        self.assertIn("consumes", kinds)


if __name__ == "__main__":
    unittest.main()

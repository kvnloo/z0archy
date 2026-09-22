import unittest

from z0archy_core.graph import compile_graph, zid


class SemanticGraphTests(unittest.TestCase):
    def test_harness_mechanism_and_lifecycle_nodes(self):
        graph = compile_graph(
            {"components": {"runtime": {"name": "Runtime", "repo": "o/runtime"}}},
            {"interfaces": {}},
            {"profiles": {}},
            {},
            {"harnesses": {
                "h": {"name": "Harness", "repo": "o/h", "component": "runtime"}
            }},
            {"mechanisms": {
                "m": {
                    "name": "Mechanism",
                    "family": "compression",
                    "implementations": [{"repo": "o/m", "harness": "h"}],
                }
            }},
            {"lifecycles": {
                "promotion": {
                    "name": "Promotion",
                    "owner_repo": "o/loop",
                    "stages": ["candidate", "main"],
                }
            }},
            generated_at="2026-01-01T00:00:00Z",
        )
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(zid("harness", "h"), ids)
        self.assertIn(zid("mechanism", "m"), ids)
        self.assertIn(zid("mechanism-family", "compression"), ids)
        self.assertIn(zid("lifecycle", "promotion"), ids)
        self.assertIn(zid("lifecycle-state", "promotion:candidate"), ids)
        self.assertTrue(all(e.get("provenance") for e in graph["edges"]))


if __name__ == "__main__":
    unittest.main()

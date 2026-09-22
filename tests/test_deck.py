import importlib.util
import unittest
from pathlib import Path

from z0archy_core.graph import compile_graph

spec = importlib.util.spec_from_file_location(
    "generate_deck", Path(__file__).parents[1] / "scripts" / "generate_deck.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class DeckTests(unittest.TestCase):
    def semantic_graph(self):
        return compile_graph(
            {"components": {
                "a": {
                    "name": "A", "repo": "o/a", "kind": "runtime",
                    "status": "canary", "execution": "live",
                    "depends_on": [], "integrates_with": ["b"],
                    "provides": ["evt.v1"], "consumes": [],
                    "install": {"branch": "main", "ref": "abc"},
                },
                "b": {
                    "name": "B", "repo": "o/b", "kind": "measurement",
                    "status": "experimental", "execution": "shadow",
                    "depends_on": ["a"], "integrates_with": ["a"],
                    "provides": [], "consumes": ["evt.v1"],
                },
            }},
            {"interfaces": {"evt.v1": {"owner": "a", "summary": "event"}}},
            {"profiles": {"core": {"components": ["a", "b"]}}},
            {},
            {"harnesses": {
                "h": {"name": "Harness", "repo": "o/a", "component": "a", "kind": "executor"}
            }},
            {"mechanisms": {
                "m": {
                    "name": "Mechanism",
                    "kind": "compression",
                    "purpose": "Compress context.",
                    "implementations": [{"harness": "h", "repo": "o/a"}],
                }
            }},
            {"lifecycles": {
                "promotion": {
                    "name": "Promotion",
                    "kind": "promotion",
                    "owner_repo": "o/a",
                    "stages": ["candidate", "main"],
                    "rule": "Promote with evidence.",
                }
            }},
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_deck_projects_graph_ir(self):
        deck = mod.build(self.semantic_graph())
        ids = {n["id"] for s in deck["slides"] for n in s["nodes"]}
        self.assertIn("a", ids)
        self.assertIn("iface:evt.v1", ids)
        component = next(n for s in deck["slides"] for n in s["nodes"] if n["id"] == "a")
        self.assertEqual(component["meta"]["canonicalBranch"], "main")
        self.assertEqual(component["meta"]["graphType"], "component")
        self.assertEqual(component["meta"]["semanticLevel"], 1)

    def test_deck_exposes_semantic_architecture_planes(self):
        deck = mod.build(self.semantic_graph())
        slide_ids = {s["id"] for s in deck["slides"]}
        self.assertTrue(
            {"harnesses", "mechanisms", "lifecycles", "profiles", "repositories"}.issubset(slide_ids)
        )

        node_ids = {n["id"] for s in deck["slides"] for n in s["nodes"]}
        self.assertIn("z0://harness/h", node_ids)
        self.assertIn("z0://mechanism/m", node_ids)
        self.assertIn("z0://lifecycle/promotion", node_ids)
        self.assertIn("profile:core", node_ids)
        harness = next(
            n for s in deck["slides"] for n in s["nodes"]
            if n["id"] == "z0://harness/h"
        )
        mechanism = next(
            n for s in deck["slides"] for n in s["nodes"]
            if n["id"] == "z0://mechanism/m"
        )
        self.assertEqual(harness["meta"]["semanticLevel"], 2)
        self.assertEqual(mechanism["meta"]["semanticLevel"], 2)
        self.assertIn("semanticZoom", deck["meta"])

        semantic_edges = {
            (e["from"], e["to"], e.get("label"))
            for e in deck["connections"]
        }
        self.assertIn(
            ("z0://mechanism/m", "z0://harness/h", "implemented by"),
            semantic_edges,
        )


if __name__ == "__main__":
    unittest.main()

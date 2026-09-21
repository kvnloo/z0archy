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
    def test_deck_projects_graph_ir(self):
        graph = compile_graph(
            {"components": {
                "a": {"name": "A", "repo": "o/a", "kind": "runtime", "status": "canary", "execution": "live", "depends_on": [], "integrates_with": ["b"], "provides": ["evt.v1"], "consumes": [], "install": {"branch": "main", "ref": "abc"}},
                "b": {"name": "B", "repo": "o/b", "kind": "measurement", "status": "experimental", "execution": "shadow", "depends_on": ["a"], "integrates_with": ["a"], "provides": [], "consumes": ["evt.v1"]},
            }},
            {"interfaces": {"evt.v1": {"owner": "a", "summary": "event"}}},
            {"profiles": {}}, {}, generated_at="2026-01-01T00:00:00Z",
        )
        deck = mod.build(graph)
        ids = {n["id"] for s in deck["slides"] for n in s["nodes"]}
        self.assertIn("a", ids)
        self.assertIn("iface:evt.v1", ids)
        component = next(n for s in deck["slides"] for n in s["nodes"] if n["id"] == "a")
        self.assertEqual(component["meta"]["canonicalBranch"], "main")


if __name__ == "__main__":
    unittest.main()

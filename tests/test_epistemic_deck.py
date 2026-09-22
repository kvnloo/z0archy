import importlib.util
import unittest
from pathlib import Path

from z0archy_core.epistemic import apply_epistemic_registry
from z0archy_core.graph import compile_graph

spec = importlib.util.spec_from_file_location(
    "generate_deck_epistemic", Path(__file__).parents[1] / "scripts" / "generate_deck.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EpistemicDeckTests(unittest.TestCase):
    def test_deck_exposes_information_and_evidence_planes(self):
        graph = compile_graph(
            {"components": {
                "runtime": {
                    "name": "Runtime", "repo": "o/runtime", "kind": "runtime",
                    "depends_on": [], "integrates_with": [],
                    "provides": ["evt.v1"], "consumes": [],
                }
            }},
            {"interfaces": {"evt.v1": {"owner": "runtime", "summary": "event"}}},
            {"profiles": {}},
            {},
            {},
            {"mechanisms": {
                "compressor": {
                    "name": "Compressor",
                    "kind": "compression",
                    "implementations": [{"repo": "o/runtime"}],
                }
            }},
            {},
            generated_at="2026-01-01T00:00:00Z",
        )
        graph = apply_epistemic_registry(
            graph,
            {"representations": {
                "raw": {
                    "name": "Raw", "kind": "source", "scale": "large",
                    "sensitivity": "inherited", "evidence": ["README.md"],
                },
                "compact": {
                    "name": "Compact", "kind": "decision_state", "scale": "compact",
                    "sensitivity": "inherited", "produced_by": ["compressor"],
                    "evidence": ["ARCHITECTURE.md"],
                },
            }},
            {"evidence_dependencies": {
                "compression": {
                    "from": "representation:raw",
                    "to": "representation:compact",
                    "relation": "compresses_to",
                    "via": "mechanism:compressor",
                    "required_evidence": ["ARCHITECTURE.md"],
                    "invariants": ["traceable"],
                    "invalidators": ["trace lost"],
                    "retrieval": {"fastest": "repo-doc"},
                    "confidence": "declared",
                }
            }},
        )
        deck = mod.build(graph)
        slide_ids = {slide["id"] for slide in deck["slides"]}
        self.assertIn("representations", slide_ids)
        self.assertIn("epistemic", slide_ids)

        node_ids = {node["id"] for slide in deck["slides"] for node in slide["nodes"]}
        self.assertIn("z0://representation/raw", node_ids)
        self.assertIn("z0://evidence-dependency/compression", node_ids)

        epistemic_edges = [e for e in deck["connections"] if e.get("kind") == "epistemic"]
        self.assertTrue(epistemic_edges)


if __name__ == "__main__":
    unittest.main()

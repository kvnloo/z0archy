import unittest

from z0archy_core.epistemic import apply_epistemic_registry
from z0archy_core.graph import compile_graph, zid
from z0archy_core.lint import lint_graph


class EpistemicTests(unittest.TestCase):
    def base_graph(self):
        return compile_graph(
            {
                "components": {
                    "runtime": {
                        "name": "Runtime",
                        "repo": "example/runtime",
                        "kind": "runtime",
                        "depends_on": [],
                        "integrates_with": [],
                        "provides": ["runtime.event.v1"],
                        "consumes": [],
                    }
                }
            },
            {"interfaces": {"runtime.event.v1": {"owner": "runtime", "summary": "event"}}},
            {"profiles": {}},
            {},
            {},
            {
                "mechanisms": {
                    "compressor": {
                        "name": "Compressor",
                        "kind": "compression",
                        "implementations": [{"repo": "example/runtime"}],
                    }
                }
            },
            {},
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_representation_and_evidence_dependency_become_graph_primitives(self):
        graph = apply_epistemic_registry(
            self.base_graph(),
            {
                "representations": {
                    "raw": {
                        "name": "Raw",
                        "kind": "source",
                        "scale": "large",
                        "sensitivity": "inherited",
                        "evidence": ["README.md"],
                    },
                    "compact": {
                        "name": "Compact",
                        "kind": "decision_state",
                        "scale": "compact",
                        "sensitivity": "inherited",
                        "produced_by": ["compressor"],
                        "interface": "runtime.event.v1",
                        "evidence": ["ARCHITECTURE.md"],
                    },
                }
            },
            {
                "evidence_dependencies": {
                    "compression-claim": {
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
                }
            },
        )
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(zid("representation", "raw"), ids)
        self.assertIn(zid("representation", "compact"), ids)
        self.assertIn(zid("evidence-dependency", "compression-claim"), ids)
        self.assertIn(zid("evidence-ref", "ARCHITECTURE.md"), ids)

        relation = next(e for e in graph["edges"] if e["id"] == zid("edge", "epistemic:compression-claim"))
        self.assertEqual(relation["type"], "compresses_to")
        self.assertTrue(relation["attributes"]["epistemic"])
        self.assertTrue(relation["provenance"])

        errors = [x for x in lint_graph(graph) if x["level"] == "error"]
        self.assertEqual(errors, [])

    def test_unresolved_evidence_endpoint_fails_lint(self):
        graph = apply_epistemic_registry(
            self.base_graph(),
            {},
            {
                "evidence_dependencies": {
                    "broken": {
                        "from": "representation:missing",
                        "to": "component:runtime",
                        "relation": "depends_on",
                        "required_evidence": ["README.md"],
                        "invariants": ["x"],
                        "invalidators": ["y"],
                        "retrieval": {"fastest": "repo-doc"},
                        "confidence": "declared",
                    }
                }
            },
        )
        codes = {x["code"] for x in lint_graph(graph) if x["level"] == "error"}
        self.assertIn("evidence.unresolved_endpoint", codes)


if __name__ == "__main__":
    unittest.main()

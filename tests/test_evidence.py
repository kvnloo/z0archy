import unittest

from z0archy_core.evidence import build_evidence_dependency
from z0archy_core.graph import compile_graph
from z0archy_core.lint import lint_graph


class EvidenceDependencyTests(unittest.TestCase):
    def graph(self, source_ref="a" * 40):
        return compile_graph(
            {"components": {
                "runtime": {
                    "name": "Runtime",
                    "repo": "o/runtime",
                    "depends_on": [],
                    "integrates_with": [],
                    "provides": ["evt.v1"],
                    "consumes": [],
                }
            }},
            {"interfaces": {"evt.v1": {"owner": "runtime", "summary": "event"}}},
            {"profiles": {}},
            {},
            {"harnesses": {
                "dsh": {
                    "name": "DeepSeek",
                    "repo": "o/dsh",
                    "catalog_gap": True,
                }
            }},
            {},
            {},
            source_ref=source_ref,
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_declared_relations_have_evidence_contract_without_fake_score(self):
        graph = self.graph()
        self.assertTrue(graph["edges"])
        for edge in graph["edges"]:
            dep = edge["evidenceDependency"]
            self.assertTrue(dep["requiredEvidence"])
            self.assertTrue(dep["invariants"])
            self.assertTrue(dep["invalidators"])
            self.assertTrue(dep["abstainWhen"])
            self.assertIsNone(dep["confidence"]["numericScore"])

    def test_linter_surfaces_catalog_gap_as_warning(self):
        findings = lint_graph(self.graph())
        gap = [f for f in findings if f["code"] == "harness-catalog-gap"]
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0]["severity"], "warning")
        self.assertFalse(any(f["severity"] == "error" for f in findings))

    def test_linter_warns_on_moving_canonical_ref(self):
        findings = lint_graph(self.graph(source_ref="main"))
        self.assertTrue(any(f["code"] == "moving-declared-ref" for f in findings))

    def test_confidence_is_authority_based(self):
        dep = build_evidence_dependency(
            [{
                "class": "implemented",
                "source": "o/r",
                "ref": "b" * 40,
                "path": "README.md",
                "field": "existence",
            }],
            source_id="z0://repo/o/r",
            target_id="z0://artifact/a",
            verified_at=None,
        )
        self.assertEqual(dep["confidence"]["level"], "exact-implementation")
        self.assertIsNone(dep["confidence"]["numericScore"])


if __name__ == "__main__":
    unittest.main()

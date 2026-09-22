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

    def test_information_plane_and_evidence_dependencies_are_first_class(self):
        graph = compile_graph(
            {"components": {
                "runtime": {"name": "Runtime", "repo": "o/runtime", "kind": "runtime", "depends_on": [], "integrates_with": [], "provides": [], "consumes": []},
            }},
            {"interfaces": {"decision.v1": {"owner": "runtime", "summary": "decision"}}},
            {"profiles": {}},
            {},
            {},
            {"mechanisms": {"compress": {"name": "Compress", "kind": "compression"}}},
            {},
            {"representations": {
                "raw": {"name": "Raw", "kind": "source"},
                "receipt": {"name": "Receipt", "kind": "decision", "interface": "decision.v1", "produced_by": ["compress"]},
            }},
            {"evidence_dependencies": {
                "raw-to-receipt": {
                    "from": "representation:raw",
                    "to": "representation:receipt",
                    "relation": "compresses_to",
                    "via": "mechanism:compress",
                    "required_evidence": ["doc"],
                    "invariants": ["recallable"],
                    "invalidators": ["lossy without receipt"],
                    "retrieval": {"fastest": "doc"},
                    "confidence": "declared",
                }
            }},
            generated_at="2026-01-01T00:00:00Z",
        )
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(zid("representation", "raw"), ids)
        self.assertIn(zid("representation", "receipt"), ids)
        self.assertIn(zid("evidence-dependency", "raw-to-receipt"), ids)
        evidence_edges = [e for e in graph["edges"] if e["id"] == zid("edge", "evidence:raw-to-receipt")]
        self.assertEqual(len(evidence_edges), 1)
        edge = evidence_edges[0]
        self.assertEqual(edge["type"], "compresses_to")
        self.assertEqual(edge["attributes"]["via"], "mechanism:compress")
        self.assertEqual(edge["attributes"]["invariants"], ["recallable"])
        claim_edges = {e["type"] for e in graph["edges"] if e["source"] == zid("evidence-dependency", "raw-to-receipt")}
        self.assertEqual(claim_edges, {"claims_from", "claims_to", "mediated_by"})


if __name__ == "__main__":
    unittest.main()

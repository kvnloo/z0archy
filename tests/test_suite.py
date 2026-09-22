import unittest

from z0archy_core.graph import compile_graph, zid
from z0archy_core.suite import apply_suite_registry


class SuiteRegistryTests(unittest.TestCase):
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
            {"harnesses": {
                "hermes": {"name": "Hermes", "repo": "o/hermes", "kind": "executor"}
            }},
            {"mechanisms": {
                "compact": {"name": "Compact", "kind": "compression"}
            }},
            {"lifecycles": {
                "rolling": {"name": "Rolling", "kind": "promotion", "stages": ["candidate", "main"]}
            }},
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_suite_adds_unreferenced_repository_and_typed_edges(self):
        graph = apply_suite_registry(
            self.base_graph(),
            {"repositories": {
                "plugin": {
                    "name": "Plugin",
                    "repo": "o/plugin",
                    "role": "context_extension",
                    "authority": "implementation",
                    "status": "experimental",
                    "supports_components": ["a"],
                    "extends_harnesses": ["hermes"],
                    "implements_mechanisms": ["compact"],
                    "lifecycle": "rolling",
                    "evidence": ["o/plugin:README.md"],
                }
            }},
            source_ref="main",
        )
        nodes = {n["id"]: n for n in graph["nodes"]}
        repo_id = zid("repo", "o/plugin")
        self.assertIn(repo_id, nodes)
        self.assertEqual(nodes[repo_id]["attributes"]["suiteRole"], "context_extension")
        self.assertEqual(nodes[repo_id]["attributes"]["suiteAuthority"], "implementation")
        self.assertEqual(nodes[repo_id]["attributes"]["suiteStatus"], "experimental")
        edge_types = {
            e["type"]
            for e in graph["edges"]
            if e["source"] == repo_id
        }
        self.assertEqual(
            edge_types,
            {
                "supports_component",
                "extends_harness",
                "implements_mechanism",
                "participates_in_lifecycle",
            },
        )
        self.assertEqual(graph["stats"]["suiteRepositories"], 1)


    def test_suite_repository_dependencies_are_order_independent(self):
        graph = apply_suite_registry(
            self.base_graph(),
            {"repositories": {
                "projection": {
                    "name": "Projection",
                    "repo": "o/projection",
                    "role": "architecture_projection",
                    "authority": "derived",
                    "status": "active",
                    "depends_on_repositories": ["substrate"],
                    "evidence": ["o/projection:README.md"],
                },
                "substrate": {
                    "name": "Substrate",
                    "repo": "o/substrate",
                    "upstream": "upstream/substrate",
                    "role": "temporal_graph_substrate",
                    "authority": "external_substrate",
                    "status": "active",
                    "evidence": ["o/substrate:README.md"],
                },
            }},
        )
        projection = zid("repo", "o/projection")
        substrate = zid("repo", "o/substrate")
        edges = [
            e for e in graph["edges"]
            if e["type"] == "uses_repository"
        ]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["source"], projection)
        self.assertEqual(edges[0]["target"], substrate)
        nodes = {n["id"]: n for n in graph["nodes"]}
        self.assertEqual(
            nodes[substrate]["attributes"]["suiteUpstream"],
            "upstream/substrate",
        )
        self.assertNotIn(zid("repo", "upstream/substrate"), nodes)

    def test_suite_enriches_existing_repository_without_duplicate(self):
        graph = apply_suite_registry(
            self.base_graph(),
            {"repositories": {
                "a-impl": {
                    "name": "A implementation",
                    "repo": "o/a",
                    "role": "execution_runtime",
                    "authority": "implementation",
                    "status": "active",
                    "evidence": ["o/a:README.md"],
                }
            }},
        )
        repo_nodes = [
            n for n in graph["nodes"]
            if n["id"] == zid("repo", "o/a")
        ]
        self.assertEqual(len(repo_nodes), 1)
        self.assertEqual(repo_nodes[0]["attributes"]["suiteRole"], "execution_runtime")
        self.assertTrue(
            any(p["path"] == "registry/suite.yaml" for p in repo_nodes[0]["provenance"])
        )


if __name__ == "__main__":
    unittest.main()

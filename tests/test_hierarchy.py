import unittest

from z0archy_core.hierarchy import (
    analyze_hierarchy_wave,
    episodes_from_runtime_graph,
    merge_episode_documents,
)


def declared_node(node_id, node_type="mechanism", **attrs):
    return {
        "id": node_id,
        "type": node_type,
        "label": node_id.rsplit("/", 1)[-1],
        "attributes": attrs,
        "provenance": [{
            "class": "declared",
            "source": "z0",
            "ref": "main",
            "path": "registry/test.yaml",
            "field": node_id,
        }],
    }


def edge(source, target, kind="integrates_with"):
    return {
        "id": f"edge:{source}->{target}",
        "type": kind,
        "source": source,
        "target": target,
        "provenance": [{
            "class": "declared",
            "source": "z0",
            "ref": "main",
            "path": "registry/test.yaml",
            "field": "edge",
        }],
    }


class HierarchyWaveTests(unittest.TestCase):
    def test_merge_requires_recurrence_and_shared_structure(self):
        a = "z0://mechanism/a"
        b = "z0://mechanism/b"
        c = "z0://mechanism/c"
        d = "z0://mechanism/d"
        graph = {
            "nodes": [
                declared_node(a, kind="compression", owner="Cognition"),
                declared_node(b, kind="compression", owner="Cognition"),
                declared_node(c, kind="runtime", owner="Runtime"),
                declared_node(d, kind="measurement", owner="Measurement"),
            ],
            "edges": [
                edge(a, c), edge(a, d),
                edge(b, c), edge(b, d),
            ],
        }
        episodes = {
            "episodes": [
                {"id": f"e{i}", "nodes": [a, b], "weight": 1}
                for i in range(4)
            ]
        }
        result = analyze_hierarchy_wave(graph, episodes)
        merges = [p for p in result["proposals"] if p["action"] == "merge"]
        self.assertEqual(result["decision"], "UPDATE")
        self.assertEqual(len(merges), 1)
        self.assertEqual(merges[0]["subjects"], [a, b])
        self.assertEqual(merges[0]["evidence"]["episodeJaccard"], 1.0)
        self.assertEqual(merges[0]["evidence"]["structuralJaccard"], 1.0)

    def test_split_requires_two_coherent_distinct_contexts(self):
        x = "z0://component/x"
        a = "z0://component/a"
        b = "z0://component/b"
        c = "z0://component/c"
        d = "z0://component/d"
        graph = {
            "nodes": [
                declared_node(x, "component", kind="runtime", owner="X"),
                declared_node(a, "component", kind="runtime", owner="A"),
                declared_node(b, "component", kind="runtime", owner="B"),
                declared_node(c, "component", kind="runtime", owner="C"),
                declared_node(d, "component", kind="runtime", owner="D"),
            ],
            "edges": [],
        }
        episodes = {"episodes": [
            {"id": "left-1", "nodes": [x, a, b]},
            {"id": "left-2", "nodes": [x, a, b]},
            {"id": "left-3", "nodes": [x, a, b]},
            {"id": "right-1", "nodes": [x, c, d]},
            {"id": "right-2", "nodes": [x, c, d]},
            {"id": "right-3", "nodes": [x, c, d]},
        ]}
        result = analyze_hierarchy_wave(
            graph,
            episodes,
            merge_episode_jaccard=2.0,
            merge_structural_jaccard=2.0,
        )
        splits = [
            p for p in result["proposals"]
            if p["action"] == "split" and p["subjects"] == [x]
        ]
        self.assertEqual(len(splits), 1)
        proposal = splits[0]
        self.assertGreaterEqual(proposal["evidence"]["clusterA"]["withinJaccard"], 0.99)
        self.assertGreaterEqual(proposal["evidence"]["clusterB"]["withinJaccard"], 0.99)
        self.assertEqual(proposal["evidence"]["crossJaccard"], 0.0)

    def test_prune_only_targets_unused_deprecated_or_reference_leaf(self):
        old = "z0://component/old"
        live = "z0://component/live"
        graph = {
            "nodes": [
                declared_node(old, "component", kind="runtime", status="deprecated"),
                declared_node(live, "component", kind="runtime", status="stable"),
            ],
            "edges": [edge(old, live)],
        }
        result = analyze_hierarchy_wave(graph, {"episodes": []})
        prune = [p for p in result["proposals"] if p["action"] == "prune"]
        self.assertEqual(len(prune), 1)
        self.assertEqual(prune[0]["subjects"], [old])
        self.assertEqual(result["decision"], "UPDATE")

    def test_weak_evidence_explicitly_returns_no_update(self):
        a = "z0://mechanism/a"
        b = "z0://mechanism/b"
        graph = {
            "nodes": [
                declared_node(a, kind="compression"),
                declared_node(b, kind="routing"),
            ],
            "edges": [],
        }
        result = analyze_hierarchy_wave(
            graph,
            {"episodes": [{"id": "one", "nodes": [a, b]}]},
        )
        self.assertEqual(result["decision"], "NO UPDATE")
        self.assertTrue(any(p["action"] == "no_update" for p in result["proposals"]))
        self.assertFalse(any(p["action"] in {"merge", "split", "prune"} for p in result["proposals"]))

    def test_runtime_episode_conversion_exports_only_canonical_targets(self):
        trace = "z0://runtime-trace/abc"
        event = "z0://runtime-event/abc:e1"
        runtime = {
            "nodes": [
                {"id": trace, "type": "runtime_trace"},
                {"id": event, "type": "runtime_event"},
            ],
            "edges": [
                {"source": trace, "target": event, "type": "trace_has_event"},
                {"source": event, "target": "z0://harness/omp", "type": "observed_from"},
                {
                    "source": event,
                    "target": "z0://representation/tokenomics-event",
                    "type": "instance_of",
                },
            ],
        }
        episodes = episodes_from_runtime_graph(runtime)["episodes"]
        self.assertEqual(len(episodes), 1)
        self.assertEqual(
            episodes[0]["nodes"],
            ["z0://harness/omp", "z0://representation/tokenomics-event"],
        )
        self.assertNotIn(trace, episodes[0]["nodes"])
        self.assertNotIn(event, episodes[0]["nodes"])

    def test_episode_documents_merge_by_episode_id(self):
        merged = merge_episode_documents(
            {"episodes": [{"id": "a", "nodes": ["x"], "weight": 1}]},
            {"episodes": [
                {"id": "a", "nodes": ["y"], "weight": 2},
                {"id": "b", "nodes": ["z"]},
            ]},
        )
        self.assertEqual([e["id"] for e in merged["episodes"]], ["a", "b"])
        self.assertEqual(merged["episodes"][0]["nodes"], ["y"])


if __name__ == "__main__":
    unittest.main()

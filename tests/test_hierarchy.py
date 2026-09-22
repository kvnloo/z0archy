import unittest

from z0archy_core.hierarchy import propose_hierarchy_changes


def node(node_id, node_type="mechanism", *, declared=True, kind=None, family=None):
    attrs = {}
    if kind:
        attrs["kind"] = kind
    if family:
        attrs["family"] = family
    return {
        "id": node_id,
        "type": node_type,
        "label": node_id,
        "attributes": attrs,
        "provenance": [{"class": "declared" if declared else "derived"}],
    }


def edge(edge_id, source, target, edge_type):
    return {"id": edge_id, "type": edge_type, "source": source, "target": target}


class HierarchyTests(unittest.TestCase):
    def test_declared_persistent_connected_node_is_kept(self):
        a = node("a", "component")
        b = node("b", "mechanism")
        world = {"nodes": [a, b], "edges": [edge("e", "a", "b", "implements")]}
        result = propose_hierarchy_changes([world, world, world])
        proposal = next(p for p in result["proposals"] if p["subjects"] == ["a"])
        self.assertEqual(proposal["action"], "keep")

    def test_high_degree_mixed_node_is_split_candidate(self):
        hub = node("hub", "mechanism", kind="context")
        neighbors = [
            node("c1", "component"), node("c2", "component"),
            node("h1", "harness"), node("r1", "representation"),
            node("r2", "representation"), node("m1", "mechanism"),
        ]
        types = ["implements", "uses", "produces", "consumes", "depends_on", "verified_via"]
        edges = [edge(f"e{i}", "hub", n["id"], types[i]) for i, n in enumerate(neighbors)]
        result = propose_hierarchy_changes([{"nodes": [hub, *neighbors], "edges": edges}])
        proposal = next(p for p in result["proposals"] if p["subjects"] == ["hub"])
        self.assertEqual(proposal["action"], "split")
        self.assertGreaterEqual(proposal["evidence"]["edgeTypeEntropyBits"], 1.5)

    def test_rare_isolated_derived_node_can_be_pruned(self):
        old = {"nodes": [node("stable", "component")], "edges": []}
        current = {"nodes": [node("stable", "component"), node("temp", declared=False)], "edges": []}
        result = propose_hierarchy_changes([old, old, old, current])
        proposal = next(p for p in result["proposals"] if p["subjects"] == ["temp"])
        self.assertEqual(proposal["action"], "prune")

    def test_declared_isolated_node_is_never_pruned(self):
        current = {"nodes": [node("declared-alone", "component", declared=True)], "edges": []}
        result = propose_hierarchy_changes([current])
        proposal = next(p for p in result["proposals"] if p["subjects"] == ["declared-alone"])
        self.assertNotEqual(proposal["action"], "prune")

    def test_same_family_similar_neighborhood_can_merge(self):
        left = node("left", family="sol-pi")
        right = node("right", family="sol-pi")
        shared = [node("a", "component"), node("b", "harness"), node("c", "representation")]
        edges = []
        for prefix, source in [("l", "left"), ("r", "right")]:
            for index, target in enumerate(shared):
                edges.append(edge(f"{prefix}{index}", source, target["id"], "related"))
        result = propose_hierarchy_changes([{"nodes": [left, right, *shared], "edges": edges}])
        merges = [p for p in result["proposals"] if p["action"] == "merge"]
        self.assertTrue(any(set(p["subjects"]) == {"left", "right"} for p in merges))

    def test_default_is_no_update(self):
        a = node("a", "mechanism", declared=False, kind="context")
        b = node("b", "component")
        world = {"nodes": [a, b], "edges": [edge("e", "a", "b", "implements")]}
        result = propose_hierarchy_changes([world])
        proposal = next(p for p in result["proposals"] if p["subjects"] == ["a"])
        self.assertEqual(proposal["action"], "no_update")


if __name__ == "__main__":
    unittest.main()

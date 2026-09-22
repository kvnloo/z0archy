from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Iterable

TARGET_TYPES = {"component", "harness", "mechanism", "representation"}


def propose_hierarchy_changes(
    snapshots: Iterable[dict[str, Any]],
    *,
    target_types: set[str] | None = None,
) -> dict[str, Any]:
    """Propose conservative hierarchy changes without mutating canonical truth.

    The newest snapshot is treated as current. Historical snapshots only provide
    persistence/co-occurrence evidence. Declared nodes are never prune candidates.
    """
    worlds = list(snapshots)
    if not worlds:
        raise ValueError("at least one graph snapshot is required")
    targets = target_types or TARGET_TYPES
    current = worlds[-1]
    current_nodes = {
        node["id"]: node for node in current.get("nodes") or []
        if node.get("type") in targets
    }
    current_edges = current.get("edges") or []
    history_presence = Counter()
    for world in worlds:
        ids = {node["id"] for node in world.get("nodes") or []}
        history_presence.update(ids)

    adjacency = _adjacency(current)
    node_decisions: list[dict[str, Any]] = []
    split_or_prune: set[str] = set()

    for node_id, node in sorted(current_nodes.items()):
        neighbors = adjacency.get(node_id, [])
        degree = len(neighbors)
        edge_types = Counter(row["edgeType"] for row in neighbors)
        neighbor_types = Counter(row["neighborType"] for row in neighbors)
        persistence = history_presence[node_id] / len(worlds)
        declared = _is_declared(node)
        edge_entropy = _entropy(edge_types)
        evidence = {
            "persistence": round(persistence, 3),
            "degree": degree,
            "edgeTypeEntropyBits": edge_entropy,
            "neighborTypeCount": len(neighbor_types),
            "edgeTypes": dict(sorted(edge_types.items())),
            "neighborTypes": dict(sorted(neighbor_types.items())),
            "declared": declared,
        }

        if degree >= 6 and edge_entropy >= 1.5 and len(neighbor_types) >= 3:
            action = "split"
            confidence = min(0.95, 0.55 + min(degree, 12) / 40 + min(edge_entropy, 2.5) / 10)
            reason = "High-degree concept spans multiple relation and neighbor types; inspect whether one label is carrying multiple schemas."
            split_or_prune.add(node_id)
        elif (not declared) and degree == 0 and persistence <= 0.25:
            action = "prune"
            confidence = min(0.9, 0.65 + (0.25 - persistence))
            reason = "Non-declared concept is isolated and historically rare; safe candidate for removal from derived views."
            split_or_prune.add(node_id)
        elif declared and persistence >= 0.8 and degree > 0:
            action = "keep"
            confidence = min(0.99, 0.7 + persistence * 0.25)
            reason = "Persistent declared concept remains connected across architecture history."
        else:
            action = "no_update"
            confidence = 0.7
            reason = "Current evidence does not justify restructuring this concept."

        node_decisions.append(_proposal(
            action,
            [node_id],
            confidence,
            reason,
            evidence,
        ))

    merge_candidates: list[dict[str, Any]] = []
    node_ids = sorted(current_nodes)
    for i, left_id in enumerate(node_ids):
        left = current_nodes[left_id]
        if left_id in split_or_prune:
            continue
        for right_id in node_ids[i + 1:]:
            right = current_nodes[right_id]
            if right_id in split_or_prune or left.get("type") != right.get("type"):
                continue
            group_left = _group_key(left)
            group_right = _group_key(right)
            if not group_left or group_left != group_right:
                continue
            left_neighbors = {row["neighbor"] for row in adjacency.get(left_id, [])}
            right_neighbors = {row["neighbor"] for row in adjacency.get(right_id, [])}
            jaccard = _jaccard(left_neighbors, right_neighbors)
            if jaccard < 0.75:
                continue
            confidence = min(0.97, 0.65 + jaccard * 0.3)
            merge_candidates.append(_proposal(
                "merge",
                [left_id, right_id],
                confidence,
                "Same semantic grouping and strongly overlapping graph neighborhoods suggest duplicate abstractions.",
                {
                    "group": group_left,
                    "neighborJaccard": round(jaccard, 3),
                    "leftDegree": len(left_neighbors),
                    "rightDegree": len(right_neighbors),
                },
            ))

    actions = Counter(row["action"] for row in node_decisions + merge_candidates)
    return {
        "schemaVersion": "0.1.0",
        "kind": "hierarchy-meta-proposals",
        "snapshotCount": len(worlds),
        "policy": {
            "mutatesCanonical": False,
            "declaredNodesPrunable": False,
            "mergeNeighborJaccardMin": 0.75,
            "splitDegreeMin": 6,
            "splitEdgeEntropyMinBits": 1.5,
        },
        "summary": {
            "targetNodeCount": len(current_nodes),
            "proposalCount": len(node_decisions) + len(merge_candidates),
            "actions": dict(sorted(actions.items())),
        },
        "proposals": sorted(
            [*node_decisions, *merge_candidates],
            key=lambda row: (
                {"merge": 0, "split": 1, "prune": 2, "keep": 3, "no_update": 4}.get(row["action"], 9),
                -row["confidence"],
                row["id"],
            ),
        ),
    }


def _proposal(
    action: str,
    subjects: list[str],
    confidence: float,
    reason: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    payload = json.dumps(
        {"action": action, "subjects": subjects},
        sort_keys=True,
        separators=(",", ":"),
    )
    ident = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"hierarchy:{action}:{ident}",
        "action": action,
        "subjects": subjects,
        "confidence": round(float(confidence), 3),
        "reason": reason,
        "evidence": evidence,
    }


def _adjacency(graph: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    nodes = {node["id"]: node for node in graph.get("nodes") or []}
    out: dict[str, list[dict[str, str]]] = {}
    for edge in graph.get("edges") or []:
        source, target = edge.get("source"), edge.get("target")
        if source not in nodes or target not in nodes:
            continue
        out.setdefault(source, []).append({
            "neighbor": target,
            "neighborType": str(nodes[target].get("type") or "unknown"),
            "edgeType": str(edge.get("type") or "unknown"),
        })
        out.setdefault(target, []).append({
            "neighbor": source,
            "neighborType": str(nodes[source].get("type") or "unknown"),
            "edgeType": str(edge.get("type") or "unknown"),
        })
    return out


def _is_declared(node: dict[str, Any]) -> bool:
    return any((row or {}).get("class") == "declared" for row in node.get("provenance") or [])


def _group_key(node: dict[str, Any]) -> str | None:
    attrs = node.get("attributes") or {}
    ntype = node.get("type")
    if ntype == "mechanism":
        value = attrs.get("family") or attrs.get("kind")
    elif ntype in {"component", "harness", "representation"}:
        value = attrs.get("kind")
    else:
        value = None
    return str(value) if value else None


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    value = 0.0
    for count in counts.values():
        p = count / total
        value -= p * math.log2(p)
    return round(value, 3)

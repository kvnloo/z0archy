from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Iterable


CONCEPT_TYPES = {"component", "mechanism", "representation", "interface", "harness"}
STRUCTURAL_ACTIONS = {"merge", "split", "prune"}


def analyze_hierarchy_wave(
    graph: dict[str, Any],
    episodes_doc: dict[str, Any] | None = None,
    *,
    min_support: int = 3,
    merge_episode_jaccard: float = 0.85,
    merge_structural_jaccard: float = 0.60,
    split_min_episodes: int = 6,
    max_keep: int = 20,
) -> dict[str, Any]:
    """Generate conservative hierarchy proposals from recurring concept episodes.

    Proposals are advisory. This function never mutates the graph. Structural changes
    require repeated episode evidence plus graph-shape evidence; weak evidence produces
    an explicit NO UPDATE decision.
    """
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    node_by_id = {node["id"]: node for node in nodes}
    concept_ids = {
        node["id"]
        for node in nodes
        if node.get("type") in CONCEPT_TYPES and _truth_class(node) == "declared"
    }
    neighbors: dict[str, set[str]] = {node_id: set() for node_id in concept_ids}
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source in concept_ids and target in concept_ids:
            neighbors[source].add(target)
            neighbors[target].add(source)

    episodes = _normalize_episodes(episodes_doc or {}, concept_ids)
    supports: Counter[str] = Counter()
    episode_ids_by_node: dict[str, list[str]] = defaultdict(list)
    weighted_support: Counter[str] = Counter()
    pair_weight: Counter[tuple[str, str]] = Counter()

    for episode in episodes:
        node_ids = sorted(set(episode["nodes"]))
        weight = float(episode["weight"])
        for node_id in node_ids:
            supports[node_id] += 1
            weighted_support[node_id] += weight
            episode_ids_by_node[node_id].append(episode["id"])
        for a, b in combinations(node_ids, 2):
            pair_weight[(a, b)] += weight

    merge_candidates: list[dict[str, Any]] = []
    for a, b in combinations(sorted(concept_ids), 2):
        if not _merge_compatible(node_by_id[a], node_by_id[b]):
            continue
        if supports[a] < min_support or supports[b] < min_support:
            continue
        co = pair_weight.get((a, b), 0.0)
        episode_j = _weighted_jaccard(
            co,
            weighted_support[a],
            weighted_support[b],
        )
        structural_j = _set_jaccard(
            neighbors.get(a, set()) - {b},
            neighbors.get(b, set()) - {a},
        )
        if episode_j < merge_episode_jaccard or structural_j < merge_structural_jaccard:
            continue
        shared_episodes = sorted(
            set(episode_ids_by_node[a]) & set(episode_ids_by_node[b])
        )
        confidence = round((episode_j * 0.6) + (structural_j * 0.4), 4)
        merge_candidates.append({
            "action": "merge",
            "subjects": [a, b],
            "confidence": confidence,
            "reason": "Concepts recur together and occupy nearly the same graph neighborhood.",
            "evidence": {
                "episodeJaccard": round(episode_j, 4),
                "structuralJaccard": round(structural_j, 4),
                "sharedEpisodeCount": len(shared_episodes),
                "episodeIds": shared_episodes[:24],
            },
        })

    # One concept participates in at most one merge proposal per wave. This makes the
    # wave actionable and avoids transitive pair spam.
    merge_candidates.sort(
        key=lambda row: (-row["confidence"], row["subjects"][0], row["subjects"][1])
    )
    proposals: list[dict[str, Any]] = []
    merged_nodes: set[str] = set()
    for proposal in merge_candidates:
        if any(node_id in merged_nodes for node_id in proposal["subjects"]):
            continue
        proposals.append(proposal)
        merged_nodes.update(proposal["subjects"])

    split_nodes: set[str] = set()
    for node_id in sorted(concept_ids):
        if node_id in merged_nodes or supports[node_id] < split_min_episodes:
            continue
        contexts = [
            {
                "id": episode["id"],
                "nodes": set(episode["nodes"]) - {node_id},
            }
            for episode in episodes
            if node_id in episode["nodes"] and (set(episode["nodes"]) - {node_id})
        ]
        split = _split_evidence(contexts)
        if split is None:
            continue
        proposals.append({
            "action": "split",
            "subjects": [node_id],
            "confidence": split["confidence"],
            "reason": "The concept repeatedly appears in two internally coherent but mutually distinct contexts.",
            "evidence": split,
        })
        split_nodes.add(node_id)

    pruned_nodes: set[str] = set()
    for node_id in sorted(concept_ids):
        if node_id in merged_nodes or node_id in split_nodes:
            continue
        node = node_by_id[node_id]
        attrs = node.get("attributes") or {}
        status = str(attrs.get("status") or "").lower()
        if status not in {"deprecated", "reference"}:
            continue
        if supports[node_id] != 0 or len(neighbors.get(node_id, set())) > 1:
            continue
        proposals.append({
            "action": "prune",
            "subjects": [node_id],
            "confidence": 0.9,
            "reason": "Deprecated/reference concept is absent from observed episodes and has minimal structural attachment.",
            "evidence": {
                "status": status,
                "episodeCount": 0,
                "degree": len(neighbors.get(node_id, set())),
            },
        })
        pruned_nodes.add(node_id)

    blocked = merged_nodes | split_nodes | pruned_nodes
    keep_candidates = [
        node_id
        for node_id in concept_ids
        if node_id not in blocked and supports[node_id] >= min_support
    ]
    keep_candidates.sort(key=lambda node_id: (-supports[node_id], node_id))
    for node_id in keep_candidates[:max_keep]:
        proposals.append({
            "action": "keep",
            "subjects": [node_id],
            "confidence": round(min(0.95, 0.55 + 0.05 * supports[node_id]), 4),
            "reason": "Concept recurs across episodes without enough evidence for structural change.",
            "evidence": {
                "episodeCount": supports[node_id],
                "episodeIds": episode_ids_by_node[node_id][:24],
                "degree": len(neighbors.get(node_id, set())),
                "contextEntropyBits": round(
                    _context_entropy(node_id, episodes, concept_ids),
                    4,
                ),
            },
        })

    structural = [row for row in proposals if row["action"] in STRUCTURAL_ACTIONS]
    decision = "UPDATE" if structural else "NO UPDATE"
    if not proposals:
        proposals.append({
            "action": "no_update",
            "subjects": [],
            "confidence": 1.0,
            "reason": "Insufficient recurring evidence for any hierarchy change.",
            "evidence": {
                "episodeCount": len(episodes),
                "minimumSupport": min_support,
            },
        })
    elif not structural:
        proposals.append({
            "action": "no_update",
            "subjects": [],
            "confidence": 0.95,
            "reason": "Observed recurrence supports existing concepts but not merge, split, or prune.",
            "evidence": {
                "episodeCount": len(episodes),
                "keepCount": sum(1 for row in proposals if row["action"] == "keep"),
            },
        })

    proposals.sort(key=_proposal_sort_key)
    return {
        "version": 1,
        "mode": "advisory",
        "decision": decision,
        "episodeCount": len(episodes),
        "conceptCount": len(concept_ids),
        "metrics": {
            "observedConceptCount": sum(1 for node_id in concept_ids if supports[node_id] > 0),
            "episodeConceptEntropyBits": round(_episode_concept_entropy(weighted_support), 4),
            "mergeProposalCount": sum(1 for row in proposals if row["action"] == "merge"),
            "splitProposalCount": sum(1 for row in proposals if row["action"] == "split"),
            "pruneProposalCount": sum(1 for row in proposals if row["action"] == "prune"),
            "keepProposalCount": sum(1 for row in proposals if row["action"] == "keep"),
        },
        "proposals": proposals,
    }


def episodes_from_runtime_graph(runtime_graph: dict[str, Any]) -> dict[str, Any]:
    """Convert observed runtime islands into concept episodes.

    Runtime-only nodes are traversed, but only canonical concept IDs are emitted in the
    episode. This keeps private operational detail out of slow hierarchy evidence.
    """
    nodes = runtime_graph.get("nodes") or []
    edges = runtime_graph.get("edges") or []
    runtime_ids = {node["id"] for node in nodes}
    runtime_types = {node["id"]: node.get("type") for node in nodes}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if not source or not target:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)

    seeds = [
        node_id
        for node_id, node_type in runtime_types.items()
        if node_type in {"runtime_trace", "runtime_session", "runtime_orchestration"}
    ]
    episodes: list[dict[str, Any]] = []
    for seed in sorted(seeds):
        queue = [(seed, 0)]
        visited = {seed}
        concepts: set[str] = set()
        while queue:
            current, depth = queue.pop(0)
            if depth >= 4:
                continue
            for neighbor in adjacency.get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                if neighbor in runtime_ids:
                    queue.append((neighbor, depth + 1))
                elif neighbor.startswith("z0://"):
                    concepts.add(neighbor)
        if concepts:
            episodes.append({
                "id": f"runtime:{seed}",
                "kind": "runtime",
                "nodes": sorted(concepts),
                "weight": 1.0,
            })
    return {"version": 1, "episodes": episodes}


def merge_episode_documents(*documents: dict[str, Any]) -> dict[str, Any]:
    episodes: dict[str, dict[str, Any]] = {}
    for document in documents:
        for index, raw in enumerate(document.get("episodes") or []):
            if not isinstance(raw, dict):
                continue
            episode_id = str(raw.get("id") or f"episode:{len(episodes)+index}")
            row = dict(raw)
            row["id"] = episode_id
            episodes[episode_id] = row
    return {"version": 1, "episodes": [episodes[key] for key in sorted(episodes)]}


def _normalize_episodes(document: dict[str, Any], known_ids: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(document.get("episodes") or []):
        if not isinstance(raw, dict):
            continue
        nodes = sorted({
            str(node_id)
            for node_id in raw.get("nodes") or []
            if str(node_id) in known_ids
        })
        if not nodes:
            continue
        weight = raw.get("weight", 1.0)
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 1.0
        if not math.isfinite(weight) or weight <= 0:
            weight = 1.0
        out.append({
            "id": str(raw.get("id") or f"episode:{index}"),
            "kind": str(raw.get("kind") or "unknown"),
            "nodes": nodes,
            "weight": weight,
        })
    return out


def _truth_class(node: dict[str, Any]) -> str | None:
    provenance = node.get("provenance") or []
    return str(provenance[0].get("class")) if provenance else None


def _merge_compatible(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("type") != b.get("type"):
        return False
    aa, bb = a.get("attributes") or {}, b.get("attributes") or {}
    for key in ("kind", "owner"):
        av, bv = aa.get(key), bb.get(key)
        if av and bv and av != bv:
            return False
    return True


def _weighted_jaccard(intersection: float, a: float, b: float) -> float:
    union = a + b - intersection
    return intersection / union if union > 0 else 0.0


def _set_jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _context_jaccard(a: set[str], b: set[str]) -> float:
    return _set_jaccard(a, b)


def _split_evidence(contexts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(contexts) < 6:
        return None
    best_pair: tuple[int, int] | None = None
    lowest = 2.0
    for i, j in combinations(range(len(contexts)), 2):
        score = _context_jaccard(contexts[i]["nodes"], contexts[j]["nodes"])
        if score < lowest:
            lowest = score
            best_pair = (i, j)
    if best_pair is None or lowest > 0.20:
        return None

    left_medoid = contexts[best_pair[0]]["nodes"]
    right_medoid = contexts[best_pair[1]]["nodes"]
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []
    for context in contexts:
        lscore = _context_jaccard(context["nodes"], left_medoid)
        rscore = _context_jaccard(context["nodes"], right_medoid)
        (left if lscore >= rscore else right).append(context)
    if len(left) < 2 or len(right) < 2:
        return None

    left_within = _average_pair_jaccard(left)
    right_within = _average_pair_jaccard(right)
    cross = _average_cross_jaccard(left, right)
    if min(left_within, right_within) < 0.45 or cross > 0.25:
        return None

    confidence = round(
        min(
            0.99,
            (min(left_within, right_within) * 0.55)
            + ((1.0 - cross) * 0.45),
        ),
        4,
    )
    return {
        "clusterA": {
            "episodeIds": [row["id"] for row in left],
            "topPartners": _top_context_nodes(left),
            "withinJaccard": round(left_within, 4),
        },
        "clusterB": {
            "episodeIds": [row["id"] for row in right],
            "topPartners": _top_context_nodes(right),
            "withinJaccard": round(right_within, 4),
        },
        "crossJaccard": round(cross, 4),
        "confidence": confidence,
    }


def _average_pair_jaccard(rows: list[dict[str, Any]]) -> float:
    pairs = list(combinations(rows, 2))
    if not pairs:
        return 1.0
    return sum(_context_jaccard(a["nodes"], b["nodes"]) for a, b in pairs) / len(pairs)


def _average_cross_jaccard(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]) -> float:
    pairs = [(a, b) for a in a_rows for b in b_rows]
    if not pairs:
        return 0.0
    return sum(_context_jaccard(a["nodes"], b["nodes"]) for a, b in pairs) / len(pairs)


def _top_context_nodes(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(row["nodes"])
    return [
        {"id": node_id, "count": count}
        for node_id, count in counts.most_common(limit)
    ]


def _context_entropy(node_id: str, episodes: list[dict[str, Any]], concepts: set[str]) -> float:
    counts: Counter[str] = Counter()
    for episode in episodes:
        if node_id not in episode["nodes"]:
            continue
        weight = float(episode["weight"])
        for other in episode["nodes"]:
            if other != node_id and other in concepts:
                counts[other] += weight
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    return -sum(
        (value / total) * math.log2(value / total)
        for value in counts.values()
        if value > 0
    )


def _episode_concept_entropy(weighted_support: Counter[str]) -> float:
    total = sum(weighted_support.values())
    if total <= 0:
        return 0.0
    return -sum(
        (value / total) * math.log2(value / total)
        for value in weighted_support.values()
        if value > 0
    )


def _proposal_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    order = {"merge": 0, "split": 1, "prune": 2, "keep": 3, "no_update": 4}
    subjects = ",".join(row.get("subjects") or [])
    return (order.get(row.get("action"), 9), -float(row.get("confidence") or 0), subjects)

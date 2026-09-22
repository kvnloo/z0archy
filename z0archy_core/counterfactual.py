from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from activegraph import Runtime
from activegraph.store.sqlite import SQLiteEventStore

from .history import semantic_graph_hash

COUNTERFACTUAL_PREFIX = "z0archy_cf_"


def fork_counterfactual_world(
    target_graph: dict[str, Any],
    store_path: str | Path,
    *,
    parent_run_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Fork a recorded architecture run and reconcile the fork to target_graph.

    The parent event prefix is copied by ActiveGraph. Architecture changes are then
    emitted as ordinary graph mutations on the child run, so ActiveGraph's native
    structural diff reports the divergent world while preserving lineage.
    """
    path = str(Path(store_path))
    parent_run_id = parent_run_id or latest_canonical_run_id(path)
    if not parent_run_id:
        raise ValueError("no canonical z0archy architecture run exists to fork")

    target_hash = semantic_graph_hash(target_graph)
    selection = (target_graph.get("snapshot") or {}).get("selection") or {}
    lineage_payload = json.dumps(
        {"parent": parent_run_id, "target": target_hash, "selection": selection},
        sort_keys=True,
        separators=(",", ":"),
    )
    lineage = hashlib.sha256(lineage_payload.encode("utf-8")).hexdigest()[:16]
    run_id = f"{COUNTERFACTUAL_PREFIX}{target_hash}_{lineage}"

    existing = {run.run_id for run in SQLiteEventStore.list_runs(path)}
    if run_id in existing:
        return _counterfactual_result(path, parent_run_id, run_id, target_hash, created=False)

    parent = Runtime.load(path, run_id=parent_run_id, behaviors=[])
    if not parent.graph.events:
        _close_runtime(parent)
        raise ValueError(f"parent run {parent_run_id!r} has no events")
    at_event = parent.graph.events[-1].id
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    SQLiteEventStore.fork_run(
        path,
        parent_run_id=parent_run_id,
        new_run_id=run_id,
        at_event_id=at_event,
        label=label or f"counterfactual {target_hash[:12]}",
        created_at=created_at,
    )
    fork = Runtime.load(path, run_id=run_id, behaviors=[])
    _reconcile_architecture_graph(fork, target_graph, parent_run_id, target_hash)

    store = fork.graph.store
    if not isinstance(store, SQLiteEventStore):
        _close_runtime(parent)
        _close_runtime(fork)
        raise TypeError("counterfactual architecture forks require SQLiteEventStore")
    store.put_snapshot(
        target_hash,
        json.dumps(target_graph, sort_keys=True, separators=(",", ":")),
        created_at=created_at,
    )
    result = _diff_result(parent, fork, target_hash, created=True)
    _close_runtime(parent)
    _close_runtime(fork)
    return result


def latest_canonical_run_id(store_path: str | Path) -> str | None:
    path = str(Path(store_path))
    if not Path(path).exists():
        return None
    runs = SQLiteEventStore.list_runs(path)
    candidates = [
        run for run in runs
        if run.run_id.startswith("z0archy_")
        and not run.run_id.startswith(COUNTERFACTUAL_PREFIX)
    ]
    return candidates[-1].run_id if candidates else None


def counterfactual_parts(run_id: str) -> tuple[str, str] | None:
    if not run_id.startswith(COUNTERFACTUAL_PREFIX):
        return None
    value = run_id.removeprefix(COUNTERFACTUAL_PREFIX)
    target_hash, sep, lineage = value.rpartition("_")
    if not sep or len(target_hash) != 64 or not lineage:
        return None
    return target_hash, lineage


def _reconcile_architecture_graph(
    fork: Runtime,
    target_graph: dict[str, Any],
    parent_run_id: str,
    target_hash: str,
) -> None:
    graph = fork.graph
    actor = "z0archy-counterfactual"

    roots = [obj for obj in graph.all_objects() if obj.type == "z0.architecture_snapshot"]
    if not roots:
        raise ValueError("parent run does not contain a z0.architecture_snapshot root")
    root = roots[0]

    desired_nodes = {node["id"]: node for node in target_graph.get("nodes") or []}
    desired_edges = {edge["id"]: edge for edge in target_graph.get("edges") or []}

    existing_objects = {
        str(obj.data.get("z0_id")): obj
        for obj in graph.all_objects()
        if isinstance(obj.data, dict) and obj.data.get("z0_id")
    }
    object_id_to_z0 = {obj.id: z0_id for z0_id, obj in existing_objects.items()}

    existing_relations = {
        str(rel.data.get("z0_id")): rel
        for rel in graph.all_relations()
        if rel.type != "z0.contains"
        and isinstance(rel.data, dict)
        and rel.data.get("z0_id")
    }

    # Remove semantic relations that no longer exist or whose shape changed.
    for z0_id, rel in list(existing_relations.items()):
        desired = desired_edges.get(z0_id)
        if desired is None or not _relation_matches(rel, desired, object_id_to_z0):
            graph.remove_relation(rel.id, actor=actor)
            existing_relations.pop(z0_id, None)

    # Remove semantic objects absent from the target. z0.contains cascades with them.
    for z0_id, obj in list(existing_objects.items()):
        if z0_id not in desired_nodes:
            graph.remove_object(obj.id, actor=actor)
            existing_objects.pop(z0_id, None)

    # Add or patch semantic objects while retaining ActiveGraph ids for shared nodes.
    for z0_id, node in desired_nodes.items():
        desired_data = _node_data(node)
        existing_obj = existing_objects.get(z0_id)
        evidence = _evidence_strings(node.get("provenance") or [])
        if existing_obj is None:
            created = graph.add_object(
                "z0." + str(node.get("type") or "node"),
                desired_data,
                actor=actor,
                evidence=evidence,
            )
            existing_objects[z0_id] = created
            graph.add_relation(
                root.id,
                created.id,
                "z0.contains",
                {"z0_id": f"{fork.run_id}:contains:{z0_id}"},
                actor=actor,
            )
        elif existing_obj.data != desired_data:
            graph.patch_object(
                existing_obj.id,
                desired_data,
                actor=actor,
                rationale="reconcile counterfactual architecture target",
                evidence=evidence,
            )

    # Rebuild endpoint lookup after additions/removals.
    active_objects = {
        str(obj.data.get("z0_id")): obj
        for obj in graph.all_objects()
        if isinstance(obj.data, dict) and obj.data.get("z0_id")
    }
    existing_relations = {
        str(rel.data.get("z0_id")): rel
        for rel in graph.all_relations()
        if rel.type != "z0.contains"
        and isinstance(rel.data, dict)
        and rel.data.get("z0_id")
    }
    for z0_id, edge in desired_edges.items():
        if z0_id in existing_relations:
            continue
        source = active_objects.get(str(edge.get("source")))
        target = active_objects.get(str(edge.get("target")))
        if source is None or target is None:
            continue
        graph.add_relation(
            source.id,
            target.id,
            "z0." + str(edge.get("type") or "relation"),
            _edge_data(edge),
            actor=actor,
        )

    snapshot = target_graph.get("snapshot") or {}
    graph.patch_object(
        root.id,
        {
            "semantic_hash": target_hash,
            "source": snapshot.get("source"),
            "truth_class": snapshot.get("truthClass"),
            "node_count": len(target_graph.get("nodes") or []),
            "edge_count": len(target_graph.get("edges") or []),
            "counterfactual": True,
            "counterfactual_parent_run_id": parent_run_id,
            "counterfactual_selection": snapshot.get("selection") or {},
        },
        actor=actor,
        rationale="mark fork as counterfactual architecture world",
    )
    graph.add_object(
        "z0.counterfactual_receipt",
        {
            "parent_run_id": parent_run_id,
            "target_hash": target_hash,
            "selection": snapshot.get("selection") or {},
            "declared_base": snapshot.get("declaredBase"),
        },
        actor=actor,
    )


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "z0_id": node["id"],
        "label": node.get("label"),
        "attributes": node.get("attributes") or {},
        "z0_provenance": node.get("provenance") or [],
    }


def _edge_data(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "z0_id": edge["id"],
        "attributes": edge.get("attributes") or {},
        "z0_provenance": edge.get("provenance") or [],
    }


def _relation_matches(rel: Any, edge: dict[str, Any], object_id_to_z0: dict[str, str]) -> bool:
    return (
        rel.type == "z0." + str(edge.get("type") or "relation")
        and object_id_to_z0.get(rel.source) == edge.get("source")
        and object_id_to_z0.get(rel.target) == edge.get("target")
        and rel.data == _edge_data(edge)
    )


def _evidence_strings(provenance: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in provenance:
        source = row.get("source")
        ref = row.get("ref")
        path = row.get("path")
        field = row.get("field")
        text = str(source or "")
        if ref:
            text += f"@{ref}"
        if path:
            text += (":" if text else "") + str(path)
        if field:
            text += "#" + str(field)
        if text:
            out.append(text)
    return out


def _counterfactual_result(
    path: str,
    parent_run_id: str,
    run_id: str,
    target_hash: str,
    *,
    created: bool,
) -> dict[str, Any]:
    parent = Runtime.load(path, run_id=parent_run_id, behaviors=[])
    fork = Runtime.load(path, run_id=run_id, behaviors=[])
    result = _diff_result(parent, fork, target_hash, created=created)
    _close_runtime(parent)
    _close_runtime(fork)
    return result


def _diff_result(parent: Runtime, fork: Runtime, target_hash: str, *, created: bool) -> dict[str, Any]:
    diff = parent.diff(fork)
    return {
        "created": created,
        "runId": fork.run_id,
        "parentRunId": parent.run_id,
        "targetHash": target_hash,
        "sharedEvents": len(diff.shared_events),
        "parentOnlyEvents": len(diff.parent_only_events),
        "forkOnlyEvents": len(diff.fork_only_events),
        "divergentObjects": len(diff.divergent_objects),
        "divergentRelations": len(diff.divergent_relations),
        "isIdentical": diff.is_identical,
    }


def _close_runtime(runtime: Runtime) -> None:
    store = runtime.graph.store
    if store is not None:
        store.close()

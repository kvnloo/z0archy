from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from activegraph import Graph, SQLiteEventStore

RUN_PREFIX = "z0archy_"
COUNTERFACTUAL_PREFIX = "z0archy_cf_"


def semantic_graph_hash(graph: dict[str, Any]) -> str:
    """Hash graph meaning while ignoring build-time timestamps."""
    value = json.loads(json.dumps(graph))
    (value.get("snapshot") or {}).pop("generatedAt", None)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _created_at(graph: dict[str, Any]) -> str:
    value = (graph.get("snapshot") or {}).get("generatedAt")
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _evidence(provenance: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in provenance:
        source = row.get("source")
        ref = row.get("ref")
        path = row.get("path")
        field = row.get("field")
        base = ""
        if source:
            base = str(source)
            if ref:
                base += f"@{ref}"
        if path:
            base += f":{path}" if base else str(path)
        if field:
            base += f"#{field}"
        if base:
            out.append(base)
    return out


def record_architecture_snapshot(
    graph: dict[str, Any],
    store_path: str | Path,
) -> dict[str, Any]:
    """Persist one semantic architecture state as an ActiveGraph run.

    Identical semantic graphs share a content-addressed run id and therefore do
    not append duplicate history. z0archy stable IDs remain data fields; ActiveGraph
    owns its own object/relation ids and event provenance.
    """
    path = str(Path(store_path))
    digest = semantic_graph_hash(graph)
    run_id = RUN_PREFIX + digest
    created_at = _created_at(graph)
    store = SQLiteEventStore(path, run_id)

    if store.count() > 0:
        if store.get_snapshot(digest) is None:
            store.put_snapshot(
                digest,
                json.dumps(graph, sort_keys=True, separators=(",", ":")),
                created_at=created_at,
            )
        event_count = store.count()
        store.close()
        return {
            "created": False,
            "runId": run_id,
            "hash": digest,
            "eventCount": event_count,
        }

    previous = _latest_canonical_run_id(path, exclude=run_id)

    store.upsert_run(
        parent_run_id=previous,
        label=f"architecture {digest[:12]}",
        created_at=created_at,
        goal="Materialize a provenance-preserving Zer0 architecture snapshot.",
    )
    materialized = Graph(run_id=run_id)
    materialized.attach_store(store)

    root = materialized.add_object(
        "z0.architecture_snapshot",
        {
            "semantic_hash": digest,
            "source": graph.get("snapshot", {}).get("source"),
            "truth_class": graph.get("snapshot", {}).get("truthClass"),
            "node_count": len(graph.get("nodes") or []),
            "edge_count": len(graph.get("edges") or []),
            "previous_run_id": previous,
        },
        actor="z0archy",
    )

    object_ids: dict[str, str] = {}
    for node in graph.get("nodes") or []:
        obj = materialized.add_object(
            "z0." + str(node.get("type") or "node"),
            {
                "z0_id": node["id"],
                "label": node.get("label"),
                "attributes": node.get("attributes") or {},
                "z0_provenance": node.get("provenance") or [],
            },
            actor="z0archy",
            evidence=_evidence(node.get("provenance") or []),
        )
        object_ids[node["id"]] = obj.id
        materialized.add_relation(
            root.id,
            obj.id,
            "z0.contains",
            {"z0_id": f"{run_id}:contains:{node['id']}"},
            actor="z0archy",
        )

    for edge in graph.get("edges") or []:
        source = object_ids.get(edge.get("source"))
        target = object_ids.get(edge.get("target"))
        if source is None or target is None:
            continue
        materialized.add_relation(
            source,
            target,
            "z0." + str(edge.get("type") or "relation"),
            {
                "z0_id": edge["id"],
                "attributes": edge.get("attributes") or {},
                "z0_provenance": edge.get("provenance") or [],
            },
            actor="z0archy",
        )

    store.put_snapshot(
        digest,
        json.dumps(graph, sort_keys=True, separators=(",", ":")),
        created_at=created_at,
    )
    event_count = store.count()
    store.close()
    return {
        "created": True,
        "runId": run_id,
        "hash": digest,
        "previousRunId": previous,
        "eventCount": event_count,
    }


def history_index(store_path: str | Path) -> dict[str, Any]:
    path = str(Path(store_path))
    runs = SQLiteEventStore.list_runs(path) if Path(path).exists() else []
    entries: list[dict[str, Any]] = []
    for run in runs:
        if not run.run_id.startswith(RUN_PREFIX):
            continue
        kind = "canonical"
        digest = run.run_id.removeprefix(RUN_PREFIX)
        snapshot_hash = digest
        lineage = None
        view_key = digest
        if run.run_id.startswith(COUNTERFACTUAL_PREFIX):
            value = run.run_id.removeprefix(COUNTERFACTUAL_PREFIX)
            target_hash, sep, lineage_value = value.rpartition("_")
            if not sep or len(target_hash) != 64:
                continue
            kind = "counterfactual"
            digest = target_hash
            snapshot_hash = target_hash
            lineage = lineage_value
            view_key = f"cf-{lineage_value}-{target_hash[:16]}"

        store = SQLiteEventStore(path, run.run_id)
        event_count = store.count()
        blob = store.get_snapshot(snapshot_hash)
        store.close()
        has_snapshot = blob is not None
        selection = None
        if blob is not None:
            try:
                selection = (json.loads(blob).get("snapshot") or {}).get("selection")
            except (TypeError, json.JSONDecodeError):
                selection = None
        entries.append({
            "runId": run.run_id,
            "hash": digest,
            "snapshotHash": snapshot_hash,
            "viewKey": view_key,
            "kind": kind,
            "lineage": lineage,
            "parentRunId": run.parent_run_id,
            "forkedAtEventId": run.forked_at_event_id,
            "label": run.label,
            "createdAt": run.created_at,
            "eventCount": event_count,
            "hasSnapshot": has_snapshot,
            "selection": selection,
            "snapshotPath": f"generated/history/{view_key}.json" if has_snapshot else None,
        })
    return {
        "version": 1,
        "runtime": "activegraph",
        "entries": entries,
    }


def export_history_snapshots(
    store_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    path = str(Path(store_path))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = history_index(path)
    for entry in index["entries"]:
        snapshot_hash = entry.get("snapshotHash") or entry["hash"]
        view_key = entry.get("viewKey") or entry["hash"]
        store = SQLiteEventStore(path, entry["runId"])
        blob = store.get_snapshot(snapshot_hash)
        store.close()
        if blob is None:
            continue
        target = out / f"{view_key}.json"
        target.write_text(json.dumps(json.loads(blob), indent=2) + "\n", encoding="utf-8")
    return index



def _latest_canonical_run_id(path: str, *, exclude: str | None = None) -> str | None:
    if not Path(path).exists():
        return None
    runs = SQLiteEventStore.list_runs(path)
    for run in reversed(runs):
        if run.run_id == exclude:
            continue
        if not run.run_id.startswith(RUN_PREFIX):
            continue
        if run.run_id.startswith(COUNTERFACTUAL_PREFIX):
            continue
        return run.run_id
    return None

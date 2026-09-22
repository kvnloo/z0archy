from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .graph import zid


TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "reasoning_tokens",
    "context_tokens",
    "reported_total_tokens",
)
CONTEXT_FIELDS = (
    "spilled_bytes",
    "granted_bytes",
    "reintroduced_bytes",
    "spill_count",
    "retrieval_calls",
    "worker_calls_avoided",
    "compaction_count",
    "citation_count",
    "missed_evidence_count",
    "unsupported_claim_count",
)
SAFE_AGENTTRACE_FIELDS = (
    "id", "session_id", "source", "source_tool", "model", "project", "health",
    "health_score", "duration", "duration_ms", "turns", "tokens", "input_tokens",
    "output_tokens", "cached_input_tokens", "cost", "cost_usd", "estimated_cost",
    "tool_failures", "failures", "errors", "anomalies", "started_at", "ended_at",
    "timestamp", "capability", "capability_level",
)
HARNESS_ALIASES = {
    "omp": "omp",
    "oh_my_pi": "omp",
    "oh-my-pi": "omp",
    "pi": "pi",
    "hermes": "hermes",
    "hermes_agent": "hermes",
    "hermes-agent": "hermes",
    "codex": "codex",
    "codex_cli": "codex",
    "deepseek": "deepseek",
    "deepseek-harness": "deepseek",
}


def compile_runtime_evidence(
    *,
    tokenomics_paths: Iterable[str | Path] = (),
    agenttrace_paths: Iterable[str | Path] = (),
    aodl_paths: Iterable[str | Path] = (),
    max_tokenomics_events: int = 300,
    max_agenttrace_sessions: int = 100,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compile privacy-bounded local runtime evidence into a semantic graph patch.

    Prompt, completion, tool-argument, tool-result and arbitrary free-form payload fields
    are intentionally excluded. The output carries topology, timing, usage, economics,
    verification, context pressure, model/harness identity and AODL structural state.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []

    def add_node(row: dict[str, Any]) -> None:
        nodes[row["id"]] = row

    def add_edge(
        kind: str,
        source: str,
        target: str,
        key: str,
        provenance: list[dict[str, Any]],
        attributes: dict[str, Any] | None = None,
    ) -> None:
        edge_id = zid("edge", f"runtime:{kind}:{key}")
        edges[edge_id] = {
            "id": edge_id,
            "type": kind,
            "source": source,
            "target": target,
            "attributes": attributes or {},
            "provenance": provenance,
        }

    tokenomics_records: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for raw_path in tokenomics_paths:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            diagnostics.append({"source": "tokenomics", "path": path.name, "error": "missing"})
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                diagnostics.append({
                    "source": "tokenomics", "path": path.name,
                    "line": line_no, "error": "malformed_json",
                })
                continue
            if not isinstance(event, dict) or event.get("schema") != "tokenomics.event.v0":
                continue
            tokenomics_records.append((event, [_runtime_provenance("tokenomics", path.name, f"line:{line_no}")]))
    _compile_tokenomics(
        tokenomics_records,
        nodes,
        edges,
        add_node,
        add_edge,
        max_events=max_tokenomics_events,
    )

    sessions: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for raw_path in agenttrace_paths:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            diagnostics.append({"source": "agenttrace", "path": path.name, "error": "missing"})
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            diagnostics.append({"source": "agenttrace", "path": path.name, "error": "malformed_json"})
            continue
        rows = _agenttrace_rows(value)
        for index, row in enumerate(rows):
            sessions.append((row, [_runtime_provenance("agenttrace", path.name, f"session:{index}")]))
    _compile_agenttrace(
        sessions[-max_agenttrace_sessions:],
        nodes,
        edges,
        add_node,
        add_edge,
    )

    for raw_path in aodl_paths:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            diagnostics.append({"source": "aodl", "path": path.name, "error": "missing"})
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            diagnostics.append({"source": "aodl", "path": path.name, "error": "malformed_json"})
            continue
        if not isinstance(doc, dict) or str(doc.get("specVersion")) != "0.2":
            diagnostics.append({"source": "aodl", "path": path.name, "error": "unsupported_document"})
            continue
        _compile_aodl(
            doc,
            path.name,
            nodes,
            edges,
            add_node,
            add_edge,
        )

    return {
        "schemaVersion": "0.1.0",
        "snapshot": {
            "generatedAt": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "truthClass": "observed",
            "source": {"kind": "local-runtime"},
            "privacy": "metadata-only",
        },
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(edges.values(), key=lambda row: row["id"]),
        "diagnostics": diagnostics,
        "summary": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "tokenomicsEventCount": sum(1 for n in nodes.values() if n["type"] == "runtime_event"),
            "traceCount": sum(1 for n in nodes.values() if n["type"] == "runtime_trace"),
            "agenttraceSessionCount": sum(1 for n in nodes.values() if n["type"] == "runtime_session"),
            "aodlWorldCount": sum(1 for n in nodes.values() if n["type"] == "runtime_orchestration"),
        },
    }


def _compile_tokenomics(records, nodes, edges, add_node, add_edge, *, max_events: int) -> None:
    by_trace: dict[str, list[tuple[dict[str, Any], list[dict[str, Any]]]]] = defaultdict(list)
    for event, provenance in records:
        trace_id = str(event.get("trace_id") or "")
        if trace_id:
            by_trace[trace_id].append((event, provenance))

    retained: list[tuple[dict[str, Any], list[dict[str, Any]]]] = sorted(
        records,
        key=lambda item: _number(item[0].get("ts")),
    )[-max_events:]

    span_to_node: dict[tuple[str, str], str] = {}
    retained_keys = {(str(e.get("trace_id")), str(e.get("event_id"))) for e, _ in retained}

    for trace_id, rows in by_trace.items():
        trace_id_node = zid("runtime-trace", trace_id)
        agg = _aggregate_trace([event for event, _ in rows])
        prov = rows[-1][1] if rows else []
        add_node({
            "id": trace_id_node,
            "type": "runtime_trace",
            "label": f"trace {trace_id[:8]}",
            "attributes": {"traceId": trace_id, **agg},
            "provenance": prov,
        })
        add_edge(
            "instance_of",
            trace_id_node,
            zid("representation", "observed-topology"),
            f"{trace_id}:observed-topology",
            prov,
        )

    for event, provenance in retained:
        trace_id = str(event.get("trace_id") or "")
        event_id = str(event.get("event_id") or "")
        if not trace_id or not event_id:
            continue
        node_id = zid("runtime-event", f"{trace_id}:{event_id}")
        attributes = _safe_tokenomics_event(event)
        add_node({
            "id": node_id,
            "type": "runtime_event",
            "label": f"{event.get('kind', 'event')} · {event.get('name', '')}".strip(" ·"),
            "attributes": attributes,
            "provenance": provenance,
        })
        add_edge(
            "trace_has_event",
            zid("runtime-trace", trace_id),
            node_id,
            f"{trace_id}:{event_id}",
            provenance,
        )
        add_edge(
            "instance_of",
            node_id,
            zid("representation", "tokenomics-event"),
            f"{trace_id}:{event_id}:tokenomics",
            provenance,
        )
        harness = _harness_id(event.get("harness") or event.get("service"))
        if harness:
            add_edge(
                "observed_from",
                node_id,
                zid("harness", harness),
                f"{trace_id}:{event_id}:{harness}",
                provenance,
            )
        span_id = str(event.get("span_id") or "")
        if span_id:
            span_to_node[(trace_id, span_id)] = node_id

    for event, provenance in retained:
        trace_id = str(event.get("trace_id") or "")
        event_id = str(event.get("event_id") or "")
        parent = str(event.get("parent_span_id") or "")
        child_id = zid("runtime-event", f"{trace_id}:{event_id}")
        parent_id = span_to_node.get((trace_id, parent))
        if parent_id and (trace_id, event_id) in retained_keys:
            add_edge(
                "runtime_parent",
                parent_id,
                child_id,
                f"{trace_id}:{parent}->{event_id}",
                provenance,
            )


def _aggregate_trace(events: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {field: 0 for field in TOKEN_FIELDS}
    context = {field: 0 for field in CONTEXT_FIELDS}
    cost = 0.0
    starts: list[float] = []
    ends: list[float] = []
    harnesses: set[str] = set()
    models: set[str] = set()
    statuses: Counter[str] = Counter()
    verified: bool | None = None
    verification_sources: set[str] = set()

    for event in events:
        usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        attribution = usage.get("attribution")
        if attribution in (None, "incremental"):
            for field in TOKEN_FIELDS:
                totals[field] += int(_number(usage.get(field)))
            economics = event.get("economics") if isinstance(event.get("economics"), dict) else {}
            cost += _number(economics.get("cost_usd"))
        ctx = event.get("context") if isinstance(event.get("context"), dict) else {}
        for field in CONTEXT_FIELDS:
            context[field] += int(_number(ctx.get(field)))
        if event.get("started_at") is not None:
            starts.append(_number(event.get("started_at")))
        if event.get("ended_at") is not None:
            ends.append(_number(event.get("ended_at")))
        harness = event.get("harness") or event.get("service")
        if harness:
            harnesses.add(str(harness))
        model = event.get("model")
        if isinstance(model, dict) and model.get("name"):
            provider = model.get("provider")
            models.add((str(provider) + "/" if provider else "") + str(model["name"]))
        statuses[str(event.get("status") or "unknown")] += 1
        outcome = event.get("outcome")
        if isinstance(outcome, dict) and isinstance(outcome.get("verified_success"), bool):
            verified = bool(outcome["verified_success"])
            if outcome.get("verification_source"):
                verification_sources.add(str(outcome["verification_source"]))

    return {
        "eventCount": len(events),
        "usage": {key: value for key, value in totals.items() if value},
        "context": {key: value for key, value in context.items() if value},
        "costUsd": round(cost, 8) if cost else 0,
        "wallDurationMs": (
            round((max(ends) - min(starts)) * 1000, 3)
            if starts and ends and max(ends) >= min(starts)
            else None
        ),
        "harnesses": sorted(harnesses),
        "models": sorted(models),
        "statuses": dict(statuses),
        "verifiedSuccess": verified,
        "verificationSources": sorted(verification_sources),
    }


def _safe_tokenomics_event(event: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        key: event.get(key)
        for key in (
            "schema", "kind", "name", "trace_id", "span_id", "event_id",
            "parent_span_id", "session_id", "task_id", "capability_id",
            "harness", "service", "role", "status", "started_at", "ended_at", "ts",
        )
        if event.get(key) is not None
    }
    for key in ("model", "usage", "economics", "latency", "context", "quota_before", "quota_after", "outcome", "experiment"):
        value = event.get(key)
        if isinstance(value, dict):
            out[key] = _json_scalar_tree(value)
    return out


def _compile_agenttrace(sessions, nodes, edges, add_node, add_edge) -> None:
    for index, (row, provenance) in enumerate(sessions):
        safe = {
            key: _json_scalar_tree(row.get(key))
            for key in SAFE_AGENTTRACE_FIELDS
            if row.get(key) is not None
        }
        identity = (
            row.get("id")
            or row.get("session_id")
            or _stable_json_hash(safe)[:24]
            or f"session-{index}"
        )
        node_id = zid("runtime-session", str(identity))
        label = str(row.get("source") or row.get("source_tool") or "agent session")
        add_node({
            "id": node_id,
            "type": "runtime_session",
            "label": label,
            "attributes": safe,
            "provenance": provenance,
        })
        add_edge(
            "summarizes",
            node_id,
            zid("representation", "trace-span"),
            f"{identity}:trace-span",
            provenance,
        )
        harness = _harness_id(row.get("source") or row.get("source_tool"))
        if harness:
            add_edge(
                "observed_from",
                node_id,
                zid("harness", harness),
                f"{identity}:{harness}",
                provenance,
            )


def _agenttrace_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []
    for key in ("recent_sessions", "sessions"):
        rows = value.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    overview = value.get("overview")
    if isinstance(overview, dict):
        return _agenttrace_rows(overview)
    return []


def _compile_aodl(doc, source_name, nodes, edges, add_node, add_edge) -> None:
    graph_id = str(doc.get("graphId") or _stable_json_hash(doc)[:16])
    revision = int(doc.get("revision") or 0)
    world_key = f"{graph_id}:{revision}:{str((doc.get('provenance') or {}).get('sourceHash') or '')[:16]}"
    world_id = zid("runtime-orchestration", world_key)
    provenance = [_runtime_provenance("aodl", source_name, f"graph:{graph_id}")]
    add_node({
        "id": world_id,
        "type": "runtime_orchestration",
        "label": graph_id,
        "attributes": {
            "graphId": graph_id,
            "revision": revision,
            "specVersion": doc.get("specVersion"),
            "sourceHash": (doc.get("provenance") or {}).get("sourceHash"),
            "hasPlan": isinstance(doc.get("plan"), dict),
            "hasObservedGraph": isinstance(doc.get("observedGraph"), dict),
            "eventCount": len(doc.get("eventLog") or []),
        },
        "provenance": provenance,
    })

    intent_id = _compile_aodl_graph(
        doc.get("intentGraph"),
        "intent",
        world_key,
        provenance,
        add_node,
        add_edge,
    )
    if intent_id:
        add_edge("has_intent", world_id, intent_id, f"{world_key}:intent", provenance)
        add_edge(
            "instance_of", intent_id, zid("representation", "aodl-intent"),
            f"{world_key}:aodl-intent", provenance,
        )

    plan = doc.get("plan")
    if isinstance(plan, dict):
        plan_id = zid("runtime-plan", world_key)
        add_node({
            "id": plan_id,
            "type": "runtime_plan",
            "label": "compiled plan",
            "attributes": {
                "graphId": graph_id,
                "keys": sorted(str(key) for key in plan),
                "status": plan.get("status") if isinstance(plan.get("status"), (str, int, float, bool)) else None,
                "harness": plan.get("harness") if isinstance(plan.get("harness"), str) else None,
            },
            "provenance": provenance,
        })
        add_edge("compiled_to", intent_id or world_id, plan_id, f"{world_key}:plan", provenance)
        add_edge(
            "instance_of", plan_id, zid("representation", "compiled-plan"),
            f"{world_key}:compiled-plan", provenance,
        )

    observed_id = _compile_aodl_graph(
        doc.get("observedGraph"),
        "observed",
        world_key,
        provenance,
        add_node,
        add_edge,
    )
    if observed_id:
        add_edge("has_observed", world_id, observed_id, f"{world_key}:observed", provenance)
        add_edge(
            "instance_of", observed_id, zid("representation", "observed-topology"),
            f"{world_key}:observed-topology", provenance,
        )
        if intent_id:
            add_edge(
                "observed_as", intent_id, observed_id,
                f"{world_key}:intent-observed", provenance,
            )


def _compile_aodl_graph(graph, phase, world_key, provenance, add_node, add_edge) -> str | None:
    if not isinstance(graph, dict):
        return None
    root_id = zid("runtime-topology", f"{world_key}:{phase}")
    nodes = [row for row in graph.get("nodes") or [] if isinstance(row, dict)]
    graph_edges = [row for row in graph.get("edges") or [] if isinstance(row, dict)]
    add_node({
        "id": root_id,
        "type": f"runtime_{phase}_topology",
        "label": f"{phase} topology",
        "attributes": {
            "phase": phase,
            "nodeCount": len(nodes),
            "edgeCount": len(graph_edges),
        },
        "provenance": provenance,
    })
    local_ids: dict[str, str] = {}
    for row in nodes:
        source_id = str(row.get("id") or "")
        if not source_id:
            continue
        node_id = zid("runtime-topology-node", f"{world_key}:{phase}:{source_id}")
        local_ids[source_id] = node_id
        add_node({
            "id": node_id,
            "type": "runtime_topology_node",
            "label": source_id,
            "attributes": {
                "phase": phase,
                "sourceId": source_id,
                "kind": row.get("kind"),
                "harness": row.get("harness"),
                "lifecycle": row.get("lifecycle"),
                "capabilities": [
                    str(x) for x in row.get("capabilities") or [] if isinstance(x, str)
                ],
                "authorityCeiling": [
                    str(x) for x in row.get("authorityCeiling") or [] if isinstance(x, str)
                ],
                "portCount": len(row.get("ports") or []),
            },
            "provenance": provenance,
        })
        add_edge(
            "topology_contains", root_id, node_id,
            f"{world_key}:{phase}:node:{source_id}", provenance,
        )
        harness = _harness_id(row.get("harness"))
        if harness:
            add_edge(
                "uses_harness", node_id, zid("harness", harness),
                f"{world_key}:{phase}:{source_id}:{harness}", provenance,
            )

    for row in graph_edges:
        source = local_ids.get(str(row.get("from") or ""))
        target = local_ids.get(str(row.get("to") or ""))
        if not source or not target:
            continue
        edge_id = str(row.get("id") or _stable_json_hash(row)[:16])
        add_edge(
            "topology_" + str(row.get("relation") or "edge"),
            source,
            target,
            f"{world_key}:{phase}:{edge_id}",
            provenance,
            attributes={
                "phase": phase,
                "relation": row.get("relation"),
                "delivery": _json_scalar_tree(row.get("delivery") or {}),
                "authority": _json_scalar_tree(row.get("authority") or {}),
            },
        )
    return root_id


def runtime_input_fingerprint(paths: Iterable[str | Path]) -> str:
    digest = hashlib.sha256()
    for raw in sorted(str(Path(path).expanduser()) for path in paths):
        path = Path(raw)
        digest.update(path.name.encode("utf-8"))
        if not path.is_file():
            digest.update(b"<missing>")
            continue
        stat = path.stat()
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def _runtime_provenance(source: str, path_name: str, field: str) -> dict[str, Any]:
    return {
        "class": "observed",
        "source": source,
        "ref": "local-runtime",
        "path": path_name,
        "field": field,
    }


def _harness_id(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip().lower().replace(" ", "_")
    if raw in HARNESS_ALIASES:
        return HARNESS_ALIASES[raw]
    for needle, harness in HARNESS_ALIASES.items():
        if needle in raw:
            return harness
    return None


def _json_scalar_tree(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_scalar_tree(x, depth + 1) for x in value[:32]]
    if isinstance(value, dict):
        return {
            str(key): _json_scalar_tree(item, depth + 1)
            for key, item in list(value.items())[:64]
            if not _sensitive_key(str(key))
        }
    return str(value)


def _sensitive_key(key: str) -> bool:
    low = key.lower()
    return any(part in low for part in (
        "prompt", "completion", "message", "content", "argument", "result",
        "secret", "token_value", "api_key", "password",
    ))


def _stable_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return 0.0

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .graph import zid
from .introspection import inspect_repository
from .sources import SourceProvider


def compile_virtual_snapshot(
    base_graph: dict[str, Any],
    selection: dict[str, Any],
    providers: dict[str, SourceProvider],
    *,
    resolved_refs: dict[str, str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge selected implementation evidence over one declared architecture graph."""
    graph = copy.deepcopy(base_graph)
    node_map = {n["id"]: n for n in graph.get("nodes", [])}
    edge_map = {e["id"]: e for e in graph.get("edges", [])}
    evidence: dict[str, Any] = {}
    resolved_refs = resolved_refs or {}

    for repo, spec in sorted((selection.get("repos") or {}).items()):
        if not isinstance(spec, dict):
            raise ValueError(f"selection for {repo} must be an object")
        source = spec.get("source", "github")
        ref = spec.get("ref", "HEAD")
        if source not in providers:
            raise KeyError(f"no provider configured for source {source!r}")
        provider = providers[source]

        if zid("repo", repo) not in node_map:
            node_map[zid("repo", repo)] = {
                "id": zid("repo", repo),
                "type": "repository",
                "label": repo,
                "attributes": {"repo": repo, "selectionOnly": True},
                "provenance": [{
                    "class": "derived",
                    "source": "z0archy",
                    "ref": "virtual",
                    "path": "selection",
                    "field": f"repos.{repo}",
                }],
            }

        inspection = inspect_repository(
            provider,
            repo,
            ref,
            resolved_ref=resolved_refs.get(repo),
        )
        evidence[repo] = inspection["summary"]
        for node in inspection["nodes"]:
            node_map[node["id"]] = node
        for edge in inspection["edges"]:
            edge_map[edge["id"]] = edge

    graph["nodes"] = sorted(node_map.values(), key=lambda n: n["id"])
    graph["edges"] = sorted(edge_map.values(), key=lambda e: e["id"])
    _derive_cross_repo_package_edges(graph)
    graph["snapshot"] = {
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "truthClass": "derived",
        "source": {"repo": "z0archy", "ref": "virtual"},
        "declaredBase": base_graph.get("snapshot"),
        "selection": selection,
    }
    graph["implementationEvidence"] = evidence
    return graph


def diff_graphs(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """Structural diff by stable semantic identity."""
    base_nodes = {n["id"]: n for n in base.get("nodes", [])}
    head_nodes = {n["id"]: n for n in head.get("nodes", [])}
    base_edges = {e["id"]: e for e in base.get("edges", [])}
    head_edges = {e["id"]: e for e in head.get("edges", [])}

    return {
        "nodes": _diff_maps(base_nodes, head_nodes),
        "edges": _diff_maps(base_edges, head_edges),
    }


def _diff_maps(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    base_ids, head_ids = set(base), set(head)
    common = base_ids & head_ids
    return {
        "added": [head[x] for x in sorted(head_ids - base_ids)],
        "removed": [base[x] for x in sorted(base_ids - head_ids)],
        "changed": [
            {"id": x, "before": base[x], "after": head[x]}
            for x in sorted(common)
            if base[x] != head[x]
        ],
    }


def _package_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def _derive_cross_repo_package_edges(graph: dict[str, Any]) -> None:
    """Add derived package edges only when a dependency resolves uniquely in-world.

    Package manifests are implementation evidence. Matching one package dependency to
    another selected package is a derived observation, never a canonical architecture
    declaration. Ambiguous names produce no edge.
    """
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    packages = [node for node in nodes if node.get("type") == "package"]
    by_name: dict[str, list[dict[str, Any]]] = {}
    for node in packages:
        attrs = node.get("attributes") or {}
        key = _package_key(attrs.get("name") or node.get("label"))
        if key:
            by_name.setdefault(key, []).append(node)

    existing = {edge.get("id") for edge in edges}
    derived: list[dict[str, Any]] = []
    ambiguous: set[str] = set()
    for source in packages:
        attrs = source.get("attributes") or {}
        source_repo = attrs.get("repo")
        for dependency in attrs.get("dependencies") or []:
            key = _package_key(dependency)
            targets = by_name.get(key) or []
            if len(targets) != 1:
                if len(targets) > 1:
                    ambiguous.add(str(dependency))
                continue
            target = targets[0]
            target_attrs = target.get("attributes") or {}
            target_repo = target_attrs.get("repo")
            if not source_repo or not target_repo or source_repo == target_repo:
                continue
            edge_id = zid("edge", f"derived:package:{source['id']}->{target['id']}")
            if edge_id in existing:
                continue
            source_prov = (source.get("provenance") or [{}])[0]
            derived.append({
                "id": edge_id,
                "type": "package_depends_on",
                "source": source["id"],
                "target": target["id"],
                "attributes": {
                    "derivedCrossRepo": True,
                    "dependencyName": dependency,
                    "sourceRepo": source_repo,
                    "targetRepo": target_repo,
                    "confidence": "manifest-match",
                },
                "provenance": [{
                    "class": "derived",
                    "source": "z0archy",
                    "ref": "virtual",
                    "path": source_prov.get("path") or attrs.get("sourcePath") or "package-manifest",
                    "field": f"dependency:{dependency}",
                    "evidenceRef": source_prov,
                }],
            })
            existing.add(edge_id)

    if derived:
        edges.extend(derived)
        edges.sort(key=lambda edge: edge["id"])
    graph.setdefault("derivedEvidence", {})["crossRepoPackageEdges"] = len(derived)
    graph["derivedEvidence"]["ambiguousPackageNames"] = sorted(ambiguous)

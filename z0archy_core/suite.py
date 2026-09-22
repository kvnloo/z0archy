from __future__ import annotations

from typing import Any

from .graph import zid


def apply_suite_registry(
    graph: dict[str, Any],
    suite_doc: dict[str, Any] | None,
    *,
    source_repo: str = "kvnloo/z0",
    source_ref: str = "main",
) -> dict[str, Any]:
    """Add canonical suite-repository roles without promoting repos to components."""
    repositories = (suite_doc or {}).get("repositories") or {}
    node_map = {node["id"]: node for node in graph.get("nodes") or []}
    edge_map = {edge["id"]: edge for edge in graph.get("edges") or []}

    def provenance(field: str) -> list[dict[str, Any]]:
        return [{
            "class": "declared",
            "source": source_repo,
            "ref": source_ref,
            "path": "registry/suite.yaml",
            "field": field,
        }]

    def add_edge(edge_type: str, source: str, target: str, key: str, field: str) -> None:
        edge_id = zid("edge", f"suite:{edge_type}:{key}")
        if edge_id in edge_map:
            return
        edge_map[edge_id] = {
            "id": edge_id,
            "type": edge_type,
            "source": source,
            "target": target,
            "attributes": {"suiteRelation": True},
            "provenance": provenance(field),
        }

    for sid, raw in repositories.items():
        spec = dict(raw or {})
        repo_name = str(spec.get("repo") or "")
        if not repo_name:
            continue
        repo_id = zid("repo", repo_name)
        existing = node_map.get(repo_id)
        attrs = {
            "repo": repo_name,
            "suite_id": sid,
            "suiteRole": spec.get("role"),
            "suiteAuthority": spec.get("authority"),
            "suiteStatus": spec.get("status"),
            "suiteSummary": spec.get("summary"),
            "suiteEvidence": spec.get("evidence") or [],
        }
        if existing is None:
            node_map[repo_id] = {
                "id": repo_id,
                "type": "repository",
                "label": spec.get("name") or repo_name,
                "attributes": attrs,
                "provenance": provenance(f"repositories.{sid}"),
            }
        else:
            existing.setdefault("attributes", {}).update({
                key: value for key, value in attrs.items() if value not in (None, [], "")
            })
            existing["label"] = spec.get("name") or existing.get("label") or repo_name
            existing.setdefault("provenance", [])
            for row in provenance(f"repositories.{sid}"):
                if row not in existing["provenance"]:
                    existing["provenance"].append(row)

        for cid in spec.get("supports_components") or []:
            target = zid("component", cid)
            if target in node_map:
                add_edge(
                    "supports_component",
                    repo_id,
                    target,
                    f"{sid}:component:{cid}",
                    f"repositories.{sid}.supports_components",
                )
        for hid in spec.get("extends_harnesses") or []:
            target = zid("harness", hid)
            if target in node_map:
                add_edge(
                    "extends_harness",
                    repo_id,
                    target,
                    f"{sid}:harness:{hid}",
                    f"repositories.{sid}.extends_harnesses",
                )
        for mid in spec.get("implements_mechanisms") or []:
            target = zid("mechanism", mid)
            if target in node_map:
                add_edge(
                    "implements_mechanism",
                    repo_id,
                    target,
                    f"{sid}:mechanism:{mid}",
                    f"repositories.{sid}.implements_mechanisms",
                )
        lifecycle = spec.get("lifecycle")
        if lifecycle:
            target = zid("lifecycle", lifecycle)
            if target in node_map:
                add_edge(
                    "participates_in_lifecycle",
                    repo_id,
                    target,
                    f"{sid}:lifecycle:{lifecycle}",
                    f"repositories.{sid}.lifecycle",
                )

    graph["nodes"] = sorted(node_map.values(), key=lambda node: node["id"])
    graph["edges"] = sorted(edge_map.values(), key=lambda edge: edge["id"])
    graph.setdefault("stats", {})["suiteRepositories"] = len(repositories)
    return graph

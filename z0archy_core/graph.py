from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

SCHEMA_VERSION = "0.1.0"


def zid(kind: str, value: str) -> str:
    return f"z0://{kind}/{quote(value, safe='/.@:-')}"


def compile_graph(
    components_doc: dict[str, Any],
    interfaces_doc: dict[str, Any],
    profiles_doc: dict[str, Any] | None = None,
    maturity_doc: dict[str, Any] | None = None,
    *,
    source_repo: str = "kvnloo/z0",
    source_ref: str = "main",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    components = components_doc.get("components") or {}
    interfaces = interfaces_doc.get("interfaces") or {}
    profiles = (profiles_doc or {}).get("profiles") or {}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def provenance(path: str, field: str) -> list[dict[str, Any]]:
        return [{
            "class": "declared",
            "source": source_repo,
            "ref": source_ref,
            "path": path,
            "field": field,
        }]

    repo_seen: set[str] = set()
    for cid, raw in components.items():
        c = dict(raw or {})
        repo_name = c.get("repo")
        nodes.append({
            "id": zid("component", cid),
            "type": "component",
            "label": c.get("name") or cid,
            "attributes": {"component_id": cid, **c},
            "provenance": provenance("registry/components.yaml", f"components.{cid}"),
        })
        if repo_name and repo_name not in repo_seen:
            repo_seen.add(repo_name)
            nodes.append({
                "id": zid("repo", repo_name),
                "type": "repository",
                "label": repo_name,
                "attributes": {"repo": repo_name},
                "provenance": provenance("registry/components.yaml", f"components.{cid}.repo"),
            })
        if repo_name:
            edges.append(_edge("implemented_by", zid("component", cid), zid("repo", repo_name), cid, "repo"))

    for name, raw in interfaces.items():
        spec = dict(raw or {})
        nodes.append({
            "id": zid("interface", name),
            "type": "interface",
            "label": name,
            "attributes": {"interface": name, **spec},
            "provenance": provenance("registry/interfaces.yaml", f"interfaces.{name}"),
        })

    for pid, raw in profiles.items():
        spec = dict(raw or {})
        nodes.append({
            "id": zid("profile", pid),
            "type": "profile",
            "label": pid,
            "attributes": {"profile_id": pid, **spec},
            "provenance": provenance("registry/profiles.yaml", f"profiles.{pid}"),
        })
        if spec.get("extends"):
            edges.append(_edge("extends", zid("profile", pid), zid("profile", spec["extends"]), pid, spec["extends"]))
        for cid in spec.get("components") or []:
            if cid in components:
                edges.append(_edge("includes", zid("profile", pid), zid("component", cid), pid, cid))

    seen_integrations: set[tuple[str, str]] = set()
    for cid, raw in components.items():
        c = raw or {}
        for dep in c.get("depends_on") or []:
            if dep in components:
                edges.append(_edge("depends_on", zid("component", cid), zid("component", dep), cid, dep))
        for other in c.get("integrates_with") or []:
            if other not in components:
                continue
            key = tuple(sorted((cid, other)))
            if key in seen_integrations:
                continue
            seen_integrations.add(key)
            a, b = key
            edges.append(_edge("integrates_with", zid("component", a), zid("component", b), a, b))
        for iface in c.get("provides") or []:
            if iface in interfaces:
                edges.append(_edge("provides", zid("component", cid), zid("interface", iface), cid, iface))
        for iface in c.get("consumes") or []:
            if iface in interfaces:
                edges.append(_edge("consumes", zid("interface", iface), zid("component", cid), iface, cid))

    nodes.sort(key=lambda n: n["id"])
    edges.sort(key=lambda e: e["id"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "snapshot": {
            "generatedAt": generated_at,
            "truthClass": "declared",
            "source": {"repo": source_repo, "ref": source_ref},
        },
        "vocabulary": {"maturity": maturity_doc or {}},
        "nodes": nodes,
        "edges": edges,
    }


def _edge(kind: str, source: str, target: str, source_key: str, target_key: str) -> dict[str, Any]:
    return {
        "id": zid("edge", f"{kind}:{source_key}->{target_key}"),
        "type": kind,
        "source": source,
        "target": target,
    }

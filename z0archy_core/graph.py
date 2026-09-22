from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

SCHEMA_VERSION = "0.2.0"


def zid(kind: str, value: str) -> str:
    return f"z0://{kind}/{quote(value, safe='/.@:-')}"


def endpoint_zid(endpoint: str) -> str:
    kind, sep, ident = str(endpoint).partition(":")
    if not sep or not ident:
        raise ValueError(f"invalid semantic endpoint: {endpoint!r}")
    return zid(kind, ident)


def compile_graph(
    components_doc: dict[str, Any],
    interfaces_doc: dict[str, Any],
    profiles_doc: dict[str, Any] | None = None,
    maturity_doc: dict[str, Any] | None = None,
    harnesses_doc: dict[str, Any] | None = None,
    mechanisms_doc: dict[str, Any] | None = None,
    representations_doc: dict[str, Any] | None = None,
    evidence_dependencies_doc: dict[str, Any] | None = None,
    lifecycles_doc: dict[str, Any] | None = None,
    *,
    source_repo: str = "kvnloo/z0",
    source_ref: str = "main",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    components = components_doc.get("components") or {}
    interfaces = interfaces_doc.get("interfaces") or {}
    profiles = (profiles_doc or {}).get("profiles") or {}
    harnesses = (harnesses_doc or {}).get("harnesses") or {}
    mechanisms = (mechanisms_doc or {}).get("mechanisms") or {}
    representations = (representations_doc or {}).get("representations") or {}
    evidence_dependencies = (evidence_dependencies_doc or {}).get("evidence_dependencies") or {}
    lifecycles = (lifecycles_doc or {}).get("lifecycles") or {}

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

    def add_node(kind: str, ident: str, label: str, attributes: dict[str, Any], path: str, field: str) -> None:
        nodes.append({
            "id": zid(kind, ident),
            "type": kind,
            "label": label,
            "attributes": attributes,
            "provenance": provenance(path, field),
        })

    repo_seen: set[str] = set()

    def add_repo(repo_name: str, path: str, field: str) -> None:
        if not repo_name or repo_name in repo_seen:
            return
        repo_seen.add(repo_name)
        add_node("repo", repo_name, repo_name, {"repo": repo_name}, path, field)

    for cid, raw in components.items():
        c = dict(raw or {})
        repo_name = c.get("repo")
        add_node(
            "component", cid, c.get("name") or cid, {"component_id": cid, **c},
            "registry/components.yaml", f"components.{cid}",
        )
        if repo_name:
            add_repo(repo_name, "registry/components.yaml", f"components.{cid}.repo")
            edges.append(_edge(
                "implemented_by", zid("component", cid), zid("repo", repo_name), cid, repo_name,
                provenance("registry/components.yaml", f"components.{cid}.repo"),
            ))

    for name, raw in interfaces.items():
        spec = dict(raw or {})
        add_node(
            "interface", name, name, {"interface": name, **spec},
            "registry/interfaces.yaml", f"interfaces.{name}",
        )

    for pid, raw in profiles.items():
        spec = dict(raw or {})
        add_node(
            "profile", pid, pid, {"profile_id": pid, **spec},
            "registry/profiles.yaml", f"profiles.{pid}",
        )
        if spec.get("extends"):
            edges.append(_edge(
                "extends", zid("profile", pid), zid("profile", spec["extends"]), pid, spec["extends"],
                provenance("registry/profiles.yaml", f"profiles.{pid}.extends"),
            ))
        for cid in spec.get("components") or []:
            if cid in components:
                edges.append(_edge(
                    "includes", zid("profile", pid), zid("component", cid), pid, cid,
                    provenance("registry/profiles.yaml", f"profiles.{pid}.components"),
                ))

    for hid, raw in harnesses.items():
        h = dict(raw or {})
        repo_name = h.get("repo")
        add_node(
            "harness", hid, h.get("name") or hid, {"harness_id": hid, **h},
            "registry/harnesses.yaml", f"harnesses.{hid}",
        )
        if repo_name:
            add_repo(repo_name, "registry/harnesses.yaml", f"harnesses.{hid}.repo")
            edges.append(_edge(
                "implemented_by", zid("harness", hid), zid("repo", repo_name), hid, repo_name,
                provenance("registry/harnesses.yaml", f"harnesses.{hid}.repo"),
            ))
        component = h.get("component")
        if component in components:
            edges.append(_edge(
                "runtime_surface_for", zid("harness", hid), zid("component", component), hid, component,
                provenance("registry/harnesses.yaml", f"harnesses.{hid}.component"),
            ))
        for ext in h.get("extensions") or []:
            add_repo(ext, "registry/harnesses.yaml", f"harnesses.{hid}.extensions")
            edges.append(_edge(
                "extended_by", zid("harness", hid), zid("repo", ext), hid, ext,
                provenance("registry/harnesses.yaml", f"harnesses.{hid}.extensions"),
            ))

    for mid, raw in mechanisms.items():
        m = dict(raw or {})
        add_node(
            "mechanism", mid, m.get("name") or mid, {"mechanism_id": mid, **m},
            "registry/mechanisms.yaml", f"mechanisms.{mid}",
        )
        for impl in m.get("implemented_by") or []:
            component = impl.get("component")
            repo_name = impl.get("repo")
            if component in components:
                edges.append(_edge(
                    "implements", zid("component", component), zid("mechanism", mid), component, mid,
                    provenance("registry/mechanisms.yaml", f"mechanisms.{mid}.implemented_by"),
                ))
            if repo_name:
                add_repo(repo_name, "registry/mechanisms.yaml", f"mechanisms.{mid}.implemented_by")
        for impl in m.get("implementations") or []:
            harness = impl.get("harness")
            repo_name = impl.get("repo")
            if harness in harnesses:
                edges.append(_edge(
                    "implements", zid("harness", harness), zid("mechanism", mid), harness, mid,
                    provenance("registry/mechanisms.yaml", f"mechanisms.{mid}.implementations"),
                ))
            if repo_name:
                add_repo(repo_name, "registry/mechanisms.yaml", f"mechanisms.{mid}.implementations")
                edges.append(_edge(
                    "implements", zid("repo", repo_name), zid("mechanism", mid), repo_name, mid,
                    provenance("registry/mechanisms.yaml", f"mechanisms.{mid}.implementations"),
                ))

    for rid, raw in representations.items():
        r = dict(raw or {})
        add_node(
            "representation", rid, r.get("name") or rid, {"representation_id": rid, **r},
            "registry/representations.yaml", f"representations.{rid}",
        )
        for mid in r.get("produced_by") or []:
            if mid in mechanisms:
                edges.append(_edge(
                    "produces", zid("mechanism", mid), zid("representation", rid), mid, rid,
                    provenance("registry/representations.yaml", f"representations.{rid}.produced_by"),
                ))
        iface = r.get("interface")
        if iface in interfaces:
            edges.append(_edge(
                "represented_by", zid("representation", rid), zid("interface", iface), rid, iface,
                provenance("registry/representations.yaml", f"representations.{rid}.interface"),
            ))

    for lid, raw in lifecycles.items():
        lifecycle = dict(raw or {})
        add_node(
            "lifecycle", lid, lifecycle.get("name") or lid, {"lifecycle_id": lid, **lifecycle},
            "registry/lifecycles.yaml", f"lifecycles.{lid}",
        )
        owner_repo = lifecycle.get("owner_repo")
        if owner_repo:
            add_repo(owner_repo, "registry/lifecycles.yaml", f"lifecycles.{lid}.owner_repo")
            edges.append(_edge(
                "owned_by", zid("lifecycle", lid), zid("repo", owner_repo), lid, owner_repo,
                provenance("registry/lifecycles.yaml", f"lifecycles.{lid}.owner_repo"),
            ))

    seen_integrations: set[tuple[str, str]] = set()
    for cid, raw in components.items():
        c = raw or {}
        for dep in c.get("depends_on") or []:
            if dep in components:
                edges.append(_edge(
                    "depends_on", zid("component", cid), zid("component", dep), cid, dep,
                    provenance("registry/components.yaml", f"components.{cid}.depends_on"),
                ))
        for other in c.get("integrates_with") or []:
            if other not in components:
                continue
            key = tuple(sorted((cid, other)))
            if key in seen_integrations:
                continue
            seen_integrations.add(key)
            a, b = key
            edges.append(_edge(
                "integrates_with", zid("component", a), zid("component", b), a, b,
                provenance("registry/components.yaml", f"components.{cid}.integrates_with"),
            ))
        for iface in c.get("provides") or []:
            if iface in interfaces:
                edges.append(_edge(
                    "provides", zid("component", cid), zid("interface", iface), cid, iface,
                    provenance("registry/components.yaml", f"components.{cid}.provides"),
                ))
        for iface in c.get("consumes") or []:
            if iface in interfaces:
                edges.append(_edge(
                    "consumes", zid("interface", iface), zid("component", cid), iface, cid,
                    provenance("registry/components.yaml", f"components.{cid}.consumes"),
                ))

    for eid, raw in evidence_dependencies.items():
        dep = dict(raw or {})
        source = endpoint_zid(dep["from"])
        target = endpoint_zid(dep["to"])
        attrs = {"evidence_dependency_id": eid, **dep}
        edges.append(_edge(
            dep.get("relation") or "evidence_dependency",
            source,
            target,
            eid,
            f"{dep['from']}->{dep['to']}",
            provenance("registry/evidence_dependencies.yaml", f"evidence_dependencies.{eid}"),
            attributes=attrs,
            edge_class="evidence",
        ))
        via = dep.get("via")
        if via:
            via_id = endpoint_zid(via)
            edges.append(_edge(
                "via", source, via_id, eid, via,
                provenance("registry/evidence_dependencies.yaml", f"evidence_dependencies.{eid}.via"),
                attributes={"evidence_dependency_id": eid},
                edge_class="evidence",
            ))

    nodes.sort(key=lambda n: n["id"])
    edges.sort(key=lambda e: e["id"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "snapshot": {
            "generatedAt": generated_at,
            "truthClass": "declared",
            "source": {"repo": source_repo, "ref": source_ref},
        },
        "vocabulary": {
            "maturity": maturity_doc or {},
            "truthClasses": ["declared", "implemented", "observed", "historical", "derived"],
        },
        "stats": {
            "components": len(components),
            "interfaces": len(interfaces),
            "profiles": len(profiles),
            "harnesses": len(harnesses),
            "mechanisms": len(mechanisms),
            "representations": len(representations),
            "evidenceDependencies": len(evidence_dependencies),
            "lifecycles": len(lifecycles),
        },
        "nodes": nodes,
        "edges": edges,
    }


def _edge(
    kind: str,
    source: str,
    target: str,
    source_key: str,
    target_key: str,
    provenance: list[dict[str, Any]] | None = None,
    *,
    attributes: dict[str, Any] | None = None,
    edge_class: str = "semantic",
) -> dict[str, Any]:
    return {
        "id": zid("edge", f"{kind}:{source_key}->{target_key}"),
        "type": kind,
        "class": edge_class,
        "source": source,
        "target": target,
        "attributes": attributes or {},
        "provenance": provenance or [],
    }

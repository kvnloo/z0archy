from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

SCHEMA_VERSION = "0.2.0"


def zid(kind: str, value: str) -> str:
    return f"z0://{kind}/{quote(value, safe='/.@:-')}"


def compile_graph(
    components_doc: dict[str, Any],
    interfaces_doc: dict[str, Any],
    profiles_doc: dict[str, Any] | None = None,
    maturity_doc: dict[str, Any] | None = None,
    harnesses_doc: dict[str, Any] | None = None,
    mechanisms_doc: dict[str, Any] | None = None,
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
    lifecycles = (lifecycles_doc or {}).get("lifecycles") or {}

    node_map: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def provenance(path: str, field: str) -> list[dict[str, Any]]:
        return [{
            "class": "declared",
            "source": source_repo,
            "ref": source_ref,
            "path": path,
            "field": field,
        }]

    def add_node(
        node_id: str,
        node_type: str,
        label: str,
        attributes: dict[str, Any],
        *,
        path: str,
        field: str,
    ) -> None:
        existing = node_map.get(node_id)
        prov = provenance(path, field)
        if existing:
            existing["provenance"].extend(
                p for p in prov if p not in existing["provenance"]
            )
            return
        node_map[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "attributes": attributes,
            "provenance": prov,
        }

    def add_repo(repo_name: str | None, *, path: str, field: str) -> str | None:
        if not repo_name:
            return None
        rid = zid("repo", repo_name)
        add_node(
            rid,
            "repository",
            repo_name,
            {"repo": repo_name},
            path=path,
            field=field,
        )
        return rid

    def add_edge(
        kind: str,
        source: str,
        target: str,
        source_key: str,
        target_key: str,
        *,
        path: str,
        field: str,
    ) -> None:
        edges.append({
            "id": zid("edge", f"{kind}:{source_key}->{target_key}"),
            "type": kind,
            "source": source,
            "target": target,
            "provenance": provenance(path, field),
        })

    # Installable product/service layer.
    for cid, raw in components.items():
        c = dict(raw or {})
        cpath = "registry/components.yaml"
        add_node(
            zid("component", cid),
            "component",
            c.get("name") or cid,
            {"component_id": cid, **c},
            path=cpath,
            field=f"components.{cid}",
        )
        repo_name = c.get("repo")
        repo_id = add_repo(repo_name, path=cpath, field=f"components.{cid}.repo")
        if repo_id:
            add_edge(
                "implemented_by",
                zid("component", cid),
                repo_id,
                cid,
                repo_name,
                path=cpath,
                field=f"components.{cid}.repo",
            )

    # Contract layer.
    for name, raw in interfaces.items():
        spec = dict(raw or {})
        ipath = "registry/interfaces.yaml"
        add_node(
            zid("interface", name),
            "interface",
            name,
            {"interface": name, **spec},
            path=ipath,
            field=f"interfaces.{name}",
        )
        owner = spec.get("owner")
        if owner in components:
            add_edge(
                "owned_by",
                zid("interface", name),
                zid("component", owner),
                name,
                owner,
                path=ipath,
                field=f"interfaces.{name}.owner",
            )

    # Install profile layer.
    for pid, raw in profiles.items():
        spec = dict(raw or {})
        ppath = "registry/profiles.yaml"
        add_node(
            zid("profile", pid),
            "profile",
            pid,
            {"profile_id": pid, **spec},
            path=ppath,
            field=f"profiles.{pid}",
        )
        if spec.get("extends"):
            parent = spec["extends"]
            add_edge(
                "extends",
                zid("profile", pid),
                zid("profile", parent),
                pid,
                parent,
                path=ppath,
                field=f"profiles.{pid}.extends",
            )
        for cid in spec.get("components") or []:
            if cid in components:
                add_edge(
                    "includes",
                    zid("profile", pid),
                    zid("component", cid),
                    pid,
                    cid,
                    path=ppath,
                    field=f"profiles.{pid}.components",
                )

    # Execution/harness layer.
    for hid, raw in harnesses.items():
        spec = dict(raw or {})
        hpath = "registry/harnesses.yaml"
        add_node(
            zid("harness", hid),
            "harness",
            spec.get("name") or hid,
            {"harness_id": hid, **spec},
            path=hpath,
            field=f"harnesses.{hid}",
        )
        repo_name = spec.get("repo")
        repo_id = add_repo(repo_name, path=hpath, field=f"harnesses.{hid}.repo")
        if repo_id:
            add_edge(
                "implemented_by",
                zid("harness", hid),
                repo_id,
                hid,
                repo_name,
                path=hpath,
                field=f"harnesses.{hid}.repo",
            )
        component = spec.get("component")
        if component in components:
            add_edge(
                "runtime_surface_of",
                zid("harness", hid),
                zid("component", component),
                hid,
                component,
                path=hpath,
                field=f"harnesses.{hid}.component",
            )

    # Cross-cutting mechanism layer.
    for mid, raw in mechanisms.items():
        spec = dict(raw or {})
        mpath = "registry/mechanisms.yaml"
        add_node(
            zid("mechanism", mid),
            "mechanism",
            spec.get("name") or mid,
            {"mechanism_id": mid, **spec},
            path=mpath,
            field=f"mechanisms.{mid}",
        )
        family = spec.get("family")
        if family:
            add_node(
                zid("mechanism-family", family),
                "mechanism_family",
                family,
                {"family_id": family},
                path=mpath,
                field=f"mechanisms.{mid}.family",
            )
            add_edge(
                "member_of",
                zid("mechanism", mid),
                zid("mechanism-family", family),
                mid,
                family,
                path=mpath,
                field=f"mechanisms.{mid}.family",
            )

        rows = list(spec.get("implemented_by") or []) + list(spec.get("implementations") or [])
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            component = row.get("component")
            harness = row.get("harness")
            repo_name = row.get("repo")
            field = f"mechanisms.{mid}.implementation[{i}]"
            if component in components:
                add_edge(
                    "implemented_by",
                    zid("mechanism", mid),
                    zid("component", component),
                    mid,
                    component,
                    path=mpath,
                    field=field,
                )
            if harness in harnesses:
                add_edge(
                    "implemented_by",
                    zid("mechanism", mid),
                    zid("harness", harness),
                    mid,
                    harness,
                    path=mpath,
                    field=field,
                )
            repo_id = add_repo(repo_name, path=mpath, field=field)
            if repo_id:
                add_edge(
                    "implemented_in_repo",
                    zid("mechanism", mid),
                    repo_id,
                    mid,
                    repo_name,
                    path=mpath,
                    field=field,
                )

    # Promotion/history/state-machine layer.
    for lid, raw in lifecycles.items():
        spec = dict(raw or {})
        lpath = "registry/lifecycles.yaml"
        add_node(
            zid("lifecycle", lid),
            "lifecycle",
            spec.get("name") or lid,
            {"lifecycle_id": lid, **spec},
            path=lpath,
            field=f"lifecycles.{lid}",
        )
        owner_repo = spec.get("owner_repo")
        repo_id = add_repo(owner_repo, path=lpath, field=f"lifecycles.{lid}.owner_repo")
        if repo_id:
            add_edge(
                "owned_by",
                zid("lifecycle", lid),
                repo_id,
                lid,
                owner_repo,
                path=lpath,
                field=f"lifecycles.{lid}.owner_repo",
            )
        previous_id: str | None = None
        previous_stage: str | None = None
        for stage in spec.get("stages") or []:
            sid = zid("lifecycle-state", f"{lid}:{stage}")
            add_node(
                sid,
                "lifecycle_state",
                stage,
                {"lifecycle": lid, "stage": stage},
                path=lpath,
                field=f"lifecycles.{lid}.stages",
            )
            add_edge(
                "has_stage",
                zid("lifecycle", lid),
                sid,
                lid,
                stage,
                path=lpath,
                field=f"lifecycles.{lid}.stages",
            )
            if previous_id is not None and previous_stage is not None:
                add_edge(
                    "next",
                    previous_id,
                    sid,
                    f"{lid}:{previous_stage}",
                    f"{lid}:{stage}",
                    path=lpath,
                    field=f"lifecycles.{lid}.stages",
                )
            previous_id = sid
            previous_stage = stage

    # Declared component relationships.
    seen_integrations: set[tuple[str, str]] = set()
    for cid, raw in components.items():
        c = raw or {}
        cpath = "registry/components.yaml"
        for dep in c.get("depends_on") or []:
            if dep in components:
                add_edge(
                    "depends_on",
                    zid("component", cid),
                    zid("component", dep),
                    cid,
                    dep,
                    path=cpath,
                    field=f"components.{cid}.depends_on",
                )
        for other in c.get("integrates_with") or []:
            if other not in components:
                continue
            key = tuple(sorted((cid, other)))
            if key in seen_integrations:
                continue
            seen_integrations.add(key)
            a, b = key
            add_edge(
                "integrates_with",
                zid("component", a),
                zid("component", b),
                a,
                b,
                path=cpath,
                field=f"components.{cid}.integrates_with",
            )
        for iface in c.get("provides") or []:
            if iface in interfaces:
                add_edge(
                    "provides",
                    zid("component", cid),
                    zid("interface", iface),
                    cid,
                    iface,
                    path=cpath,
                    field=f"components.{cid}.provides",
                )
        for iface in c.get("consumes") or []:
            if iface in interfaces:
                add_edge(
                    "consumes",
                    zid("interface", iface),
                    zid("component", cid),
                    iface,
                    cid,
                    path=cpath,
                    field=f"components.{cid}.consumes",
                )

    nodes = sorted(node_map.values(), key=lambda n: n["id"])
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

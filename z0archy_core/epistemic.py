from __future__ import annotations

from typing import Any

from .graph import zid

_ALLOWED_ENDPOINTS = {
    "component": "component",
    "harness": "harness",
    "mechanism": "mechanism",
    "interface": "interface",
    "lifecycle": "lifecycle",
    "representation": "representation",
    "repo": "repo",
}


def endpoint_id(endpoint: str) -> str | None:
    kind, sep, ident = str(endpoint).partition(":")
    if not sep or not ident or kind not in _ALLOWED_ENDPOINTS:
        return None
    return zid(_ALLOWED_ENDPOINTS[kind], ident)


def apply_epistemic_registry(
    graph: dict[str, Any],
    representations_doc: dict[str, Any] | None,
    evidence_dependencies_doc: dict[str, Any] | None,
    *,
    source_repo: str = "kvnloo/z0",
    source_ref: str = "main",
) -> dict[str, Any]:
    """Add information representations and evidence-backed semantic claims.

    These registries are projections of canonical z0 declarations. They augment the
    architecture graph without replacing ordinary dependency/data-flow relations.
    """
    node_map = {node["id"]: node for node in graph.get("nodes") or []}
    edge_map = {edge["id"]: edge for edge in graph.get("edges") or []}

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
        if existing is not None:
            existing.setdefault("provenance", [])
            existing["provenance"].extend(p for p in prov if p not in existing["provenance"])
            existing.setdefault("attributes", {}).update(
                {k: v for k, v in attributes.items() if k not in existing["attributes"]}
            )
            return
        node_map[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "attributes": attributes,
            "provenance": prov,
        }

    def add_edge(
        edge_id: str,
        edge_type: str,
        source: str,
        target: str,
        *,
        path: str,
        field: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        if edge_id in edge_map:
            return
        edge = {
            "id": edge_id,
            "type": edge_type,
            "source": source,
            "target": target,
            "provenance": provenance(path, field),
        }
        if attributes:
            edge["attributes"] = attributes
        edge_map[edge_id] = edge

    representations = (representations_doc or {}).get("representations") or {}
    rpath = "registry/representations.yaml"
    for rid, raw in representations.items():
        spec = dict(raw or {})
        rep_id = zid("representation", rid)
        add_node(
            rep_id,
            "representation",
            spec.get("name") or rid,
            {"representation_id": rid, **spec},
            path=rpath,
            field=f"representations.{rid}",
        )
        for mechanism in spec.get("produced_by") or []:
            mid = zid("mechanism", mechanism)
            if mid in node_map:
                add_edge(
                    zid("edge", f"produces-representation:{mechanism}->{rid}"),
                    "produces_representation",
                    mid,
                    rep_id,
                    path=rpath,
                    field=f"representations.{rid}.produced_by",
                )
        iface = spec.get("interface")
        if iface:
            iid = zid("interface", iface)
            if iid in node_map:
                add_edge(
                    zid("edge", f"encoded-as:{rid}->{iface}"),
                    "encoded_as",
                    rep_id,
                    iid,
                    path=rpath,
                    field=f"representations.{rid}.interface",
                )

    dependencies = (evidence_dependencies_doc or {}).get("evidence_dependencies") or {}
    dpath = "registry/evidence_dependencies.yaml"
    for did, raw in dependencies.items():
        spec = dict(raw or {})
        dep_id = zid("evidence-dependency", did)
        from_raw = str(spec.get("from") or "")
        to_raw = str(spec.get("to") or "")
        from_id = endpoint_id(from_raw)
        to_id = endpoint_id(to_raw)
        unresolved: list[str] = []
        if from_id is None or from_id not in node_map:
            unresolved.append(from_raw or "<missing from>")
        if to_id is None or to_id not in node_map:
            unresolved.append(to_raw or "<missing to>")

        attrs = {"evidence_dependency_id": did, **spec}
        if unresolved:
            attrs["unresolvedEndpoints"] = unresolved
        add_node(
            dep_id,
            "evidence_dependency",
            did,
            attrs,
            path=dpath,
            field=f"evidence_dependencies.{did}",
        )

        for ref in spec.get("required_evidence") or []:
            ref = str(ref)
            ref_id = zid("evidence-ref", ref)
            add_node(
                ref_id,
                "evidence_reference",
                ref,
                {"reference": ref},
                path=dpath,
                field=f"evidence_dependencies.{did}.required_evidence",
            )
            add_edge(
                zid("edge", f"requires-evidence:{did}->{ref}"),
                "requires_evidence",
                dep_id,
                ref_id,
                path=dpath,
                field=f"evidence_dependencies.{did}.required_evidence",
            )

        if from_id in node_map:
            add_edge(
                zid("edge", f"evidence-subject:{did}"),
                "evidence_subject",
                from_id,
                dep_id,
                path=dpath,
                field=f"evidence_dependencies.{did}.from",
            )
        if to_id in node_map:
            add_edge(
                zid("edge", f"evidence-object:{did}"),
                "evidence_object",
                dep_id,
                to_id,
                path=dpath,
                field=f"evidence_dependencies.{did}.to",
            )
        if from_id in node_map and to_id in node_map:
            relation = str(spec.get("relation") or "supported_relation")
            add_edge(
                zid("edge", f"epistemic:{did}"),
                relation,
                from_id,
                to_id,
                path=dpath,
                field=f"evidence_dependencies.{did}",
                attributes={
                    "epistemic": True,
                    "evidenceDependency": dep_id,
                    "confidence": spec.get("confidence"),
                },
            )

        via_raw = spec.get("via")
        if via_raw:
            via_id = endpoint_id(str(via_raw))
            if via_id in node_map:
                add_edge(
                    zid("edge", f"verified-via:{did}->{via_raw}"),
                    "verified_via",
                    dep_id,
                    via_id,
                    path=dpath,
                    field=f"evidence_dependencies.{did}.via",
                )
            else:
                node_map[dep_id]["attributes"].setdefault("unresolvedEndpoints", []).append(str(via_raw))

    graph["nodes"] = sorted(node_map.values(), key=lambda node: node["id"])
    graph["edges"] = sorted(edge_map.values(), key=lambda edge: edge["id"])
    graph.setdefault("vocabulary", {})["truthClasses"] = [
        "declared",
        "implemented",
        "observed",
        "historical",
        "derived",
    ]
    return graph

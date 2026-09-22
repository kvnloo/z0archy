#!/usr/bin/env python3
"""Generate z0archy/deck.json from kvnloo/z0's canonical registry."""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request
from pathlib import Path

import yaml

BASE = "https://raw.githubusercontent.com/kvnloo/z0/main"
PLANE_BY_KIND = {
    "runtime": "interaction",
    "intelligence": "decision",
    "decision": "decision",
    "contract": "decision",
    "measurement": "measurement",
    "observability": "measurement",
    "desktop": "environment",
    "compute": "compute",
    "research": "learning",
    "memory": "memory",
}
PLANES = [
    ("interaction", "Interaction + runtime", "Where users and agents actually act. OMP owns execution; learned policy does not bypass runtime authority.", [900, 1100], "runtime"),
    ("decision", "Decision + contracts", "Typed intent, bounded scorers and learned routing live here. Legal actions are filtered before learned selection.", [2500, 1100], "decision"),
    ("measurement", "Measurement + observability", "Execution facts, spans and verified outcomes stay independent from the models that made the decisions.", [4100, 1100], "measurement"),
    ("environment", "Desktop + environment", "Prediction and prepare surfaces that make the surrounding OS more agent-native without becoming the agent runtime.", [900, 2800], "environment"),
    ("compute", "Compute + placement", "Resource-aware placement and provider allocation among semantically allowed candidates.", [2500, 2800], "compute"),
    ("learning", "Learning + evidence", "Experiments, distillation and research evidence. Promotion is gated by held-out verified outcomes.", [4100, 2800], "research"),
    ("memory", "Memory", "Private durable history and episodic recall remain separate from the public research evidence base.", [900, 4500], "memory"),
]

def fetch_yaml(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": "z0archy-generator"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return yaml.safe_load(response.read().decode("utf-8"))

def grid_pos(i: int, n: int) -> list[int]:
    cols = 2 if n <= 2 else 3
    col, row = i % cols, i // cols
    width = 580 if cols == 2 else 760
    x0 = -width / 2
    step = width / max(cols - 1, 1)
    return [round(x0 + col * step), row * 260]

def deck_id_for_graph_node(node: dict) -> str:
    ntype = node.get("type")
    attrs = node.get("attributes") or {}
    if ntype == "component":
        return attrs.get("component_id") or node["id"]
    if ntype == "interface":
        return f"iface:{attrs.get('interface') or node['label']}"
    if ntype == "profile":
        return f"profile:{attrs.get('profile_id') or node['label']}"
    return node["id"]


SEMANTIC_LEVEL_BY_TYPE = {
    "root": 0,
    "component": 1,
    "mechanism_family": 1,
    "harness": 2,
    "mechanism": 2,
    "representation": 2,
    "lifecycle": 2,
    "interface": 3,
    "profile": 3,
    "repository": 3,
    "evidence_dependency": 3,
    "lifecycle_state": 4,
    "evidence_reference": 4,
    "repo_ref": 5,
    "package": 5,
    "source_artifact": 5,
    "implementation_manifest": 5,
}


def semantic_level(node_type: str) -> int:
    return SEMANTIC_LEVEL_BY_TYPE.get(node_type, 3)


def semantic_kind(node: dict) -> str:
    ntype = node.get("type")
    attrs = node.get("attributes") or {}
    if ntype == "harness":
        return "hub runtime"
    if ntype == "mechanism":
        kind = attrs.get("kind")
        if kind in {"context", "compression", "efficiency"}:
            return "hub compute"
        if kind in {"decision", "contract"}:
            return "hub decision"
        return "hub research"
    if ntype == "mechanism_family":
        return "hub contract"
    if ntype == "lifecycle":
        return "hub research"
    if ntype == "lifecycle_state":
        return "tiny contract"
    if ntype == "profile":
        return "hub environment"
    if ntype == "representation":
        kind = attrs.get("kind")
        if kind in {"measurement", "observation"}:
            return "hub measurement"
        if kind in {"decision", "decision_state", "intent", "plan"}:
            return "hub decision"
        return "hub compute"
    if ntype == "evidence_dependency":
        return "hub research"
    if ntype == "evidence_reference":
        return "tiny contract"
    if ntype == "repository":
        return "tiny contract"
    return "default"


def semantic_tip(node: dict) -> str:
    attrs = node.get("attributes") or {}
    parts = [str(node.get("label", node.get("id", ""))), "", f"type: {node.get('type','')}"]
    for key in ("kind", "adoption", "stage", "purpose", "repo", "rule", "scale", "sensitivity", "relation", "confidence"):
        value = attrs.get(key)
        if value:
            parts.append(f"{key}: {' '.join(str(value).split())}")
    prov = node.get("provenance") or []
    if prov:
        p = prov[0]
        parts.extend(["", f"declared: {p.get('source','')}@{p.get('ref','')}", f"path: {p.get('path','')}"])
    return "\n".join(parts)


def build(graph: dict | None = None) -> dict:
    if graph is None:
        component_doc = fetch_yaml("registry/components.yaml")
        interface_doc = fetch_yaml("registry/interfaces.yaml")
        components = component_doc["components"]
        interfaces = interface_doc["interfaces"]
    else:
        components = {
            n["attributes"]["component_id"]: n["attributes"]
            for n in graph.get("nodes", [])
            if n.get("type") == "component"
        }
        interfaces = {
            n["attributes"]["interface"]: n["attributes"]
            for n in graph.get("nodes", [])
            if n.get("type") == "interface"
        }

    graph_nodes = list((graph or {}).get("nodes", []))
    graph_edges = list((graph or {}).get("edges", []))
    graph_node_by_id = {n["id"]: n for n in graph_nodes}
    graph_to_deck = {n["id"]: deck_id_for_graph_node(n) for n in graph_nodes}

    plane_of = {cid: PLANE_BY_KIND.get(c.get("kind"), "decision") for cid, c in components.items()}
    component_ids = list(components)

    slides = [{
        "id": "system",
        "title": "Zer0",
        "caption": "A federation of independently useful repos joined by contracts, measurement, routing, execution and verified learning. z0 is the canonical map; z0archy is this visual projection.",
        "anchor": [2500, 250],
        "nodes": [{
            "id": "z0-root",
            "title": "Zer0",
            "sub": "canonical architecture registry",
            "body": "kvnloo/z0",
            "pos": [0, 0],
            "w": 420,
            "kind": "mega indigo",
            "tip": "Source of truth for component boundaries, profiles and cross-system interfaces. z0archy renders it; it does not replace it.",
            "meta": {"graphType": "root", "semanticLevel": 0},
        }],
        "include": component_ids,
        "layout": {"fitMargin": 180, "zoomMax": 0.72, "noCard": False},
    }]

    for pid, title, caption, anchor, style in PLANES:
        members = [(cid, c) for cid, c in components.items() if plane_of[cid] == pid]
        if not members:
            continue
        nodes = []
        for i, (cid, c) in enumerate(members):
            summary = " ".join(str(c.get("summary", "")).split())
            tip = (
                f"{summary}\n\nrepo: {c.get('repo','')}\n"
                f"status: {c.get('status','unknown')}\n"
                f"execution: {c.get('execution','unknown')}"
            )
            nodes.append({
                "id": cid,
                "title": c.get("name", cid),
                "sub": f"{c.get('kind','component')} · {c.get('status','unknown')} · {c.get('execution','unknown')}",
                "body": c.get("repo", ""),
                "pos": grid_pos(i, len(members)),
                "w": 300,
                "kind": f"hub {style}",
                "tip": tip,
                "meta": {
                    "component": cid,
                    "repo": c.get("repo"),
                    "canonicalBranch": (c.get("install") or {}).get("branch"),
                    "canonicalRef": (c.get("install") or {}).get("ref"),
                    "graphType": "component",
                    "semanticLevel": semantic_level("component"),
                },
            })
        slides.append({
            "id": pid,
            "title": title,
            "caption": caption,
            "anchor": anchor,
            "nodes": nodes,
            "layout": {"fitMargin": 150, "zoomMax": 1.0},
        })

    iface_items = list(interfaces.items())
    slides.append({
        "id": "interfaces",
        "title": "Cross-component interfaces",
        "caption": "Named contracts connect independently useful repos. Schemas remain in their owning repos; z0 owns the cross-system map.",
        "anchor": [3000, 4500],
        "nodes": [{
            "id": f"iface:{name}",
            "title": name,
            "sub": f"owner: {spec.get('owner','unknown')}",
            "body": spec.get("summary", ""),
            "pos": grid_pos(i, len(iface_items)),
            "w": 285,
            "kind": "tiny contract",
            "tip": f"{spec.get('summary','')}\n\nowner: {spec.get('owner','unknown')}",
            "meta": {"graphType": "interface", "semanticLevel": semantic_level("interface")},
        } for i, (name, spec) in enumerate(iface_items)],
        "layout": {"fitMargin": 160, "zoomMax": 0.86},
    })

    semantic_specs = [
        ("harnesses", "Execution harnesses", "The runtime surfaces Zer0 actually executes through. AODL owns portable harness ids; z0 records Zer0 adoption and role.", [5700, 1100], {"harness"}),
        ("mechanisms", "Reusable mechanisms", "Cross-cutting mechanisms remain stable semantic identities even when they are implemented in multiple harnesses or repositories.", [5700, 2800], {"mechanism", "mechanism_family"}),
        ("lifecycles", "Promotion + history", "Promotion ladders and truth states are architecture, not Git trivia. These nodes make evolution and authority explicit.", [5700, 4500], {"lifecycle", "lifecycle_state"}),
        ("profiles", "Install profiles", "Profiles are lenses over installable components; they are not a second architecture hierarchy.", [3000, 6200], {"profile"}),
        ("repositories", "Implementation repositories", "Repositories are implementation evidence containers. They remain distinct from components, harnesses and mechanisms.", [5700, 6500], {"repository"}),
        ("representations", "Information representations", "The forms information takes as it is addressed, compressed, compiled, observed and measured. This is the semantic data plane.", [900, 7900], {"representation"}),
        ("epistemic", "Evidence + belief", "EvidenceDependency nodes preserve why a relationship is believed, what would invalidate it, and the fastest path to re-verify it.", [4100, 7900], {"evidence_dependency", "evidence_reference"}),
    ]
    for sid, title, caption, anchor, types in semantic_specs:
        members = [n for n in graph_nodes if n.get("type") in types]
        if not members:
            continue
        members.sort(key=lambda n: str(n.get("label", n.get("id", ""))).lower())
        slide_nodes = []
        for i, node in enumerate(members):
            attrs = node.get("attributes") or {}
            retrieval = attrs.get("retrieval") or {}
            body = (
                attrs.get("repo")
                or attrs.get("purpose")
                or attrs.get("rule")
                or attrs.get("summary")
                or attrs.get("relation")
                or retrieval.get("fastest")
                or ""
            )
            body = " ".join(str(body).split())
            if len(body) > 110:
                body = body[:107] + "..."
            slide_nodes.append({
                "id": deck_id_for_graph_node(node),
                "title": node.get("label", node["id"]),
                "sub": node.get("type", "").replace("_", " "),
                "body": body,
                "pos": grid_pos(i, len(members)),
                "w": 320,
                "kind": semantic_kind(node),
                "tip": semantic_tip(node),
                "meta": {
                    "graphType": node.get("type"),
                    "graphId": node.get("id"),
                    "semanticLevel": semantic_level(str(node.get("type") or "")),
                },
            })
        slides.append({
            "id": sid,
            "title": title,
            "caption": caption,
            "anchor": anchor,
            "nodes": slide_nodes,
            "layout": {"fitMargin": 160, "zoomMax": 0.9},
        })

    connections = []
    seen_integrations = set()
    for cid, c in components.items():
        for dep in c.get("depends_on", []) or []:
            if dep in components:
                connections.append({"from": dep, "to": cid, "kind": "depends", "label": "depends"})
        for other in c.get("integrates_with", []) or []:
            if other not in components:
                continue
            key = tuple(sorted((cid, other)))
            if key in seen_integrations:
                continue
            seen_integrations.add(key)
            connections.append({"from": cid, "to": other, "kind": "integrates"})
        for iface in c.get("provides", []) or []:
            if iface in interfaces:
                connections.append({"from": cid, "to": f"iface:{iface}", "kind": "provides"})
        for iface in c.get("consumes", []) or []:
            if iface in interfaces:
                connections.append({"from": f"iface:{iface}", "to": cid, "kind": "consumes"})

    # Add cross-dimension semantic relations directly from graph IR. Component/interface
    # relations above keep the original presentation direction; this block focuses on
    # relations involving the richer ontology.
    existing_ids = {nd["id"] for sl in slides for nd in sl.get("nodes", [])}
    seen_semantic = set()
    for edge in graph_edges:
        source_node = graph_node_by_id.get(edge.get("source"))
        target_node = graph_node_by_id.get(edge.get("target"))
        if not source_node or not target_node:
            continue
        if source_node.get("type") in {"component", "interface"} and target_node.get("type") in {"component", "interface"}:
            continue
        src = graph_to_deck.get(edge["source"])
        dst = graph_to_deck.get(edge["target"])
        if src not in existing_ids or dst not in existing_ids:
            continue
        key = (src, dst, edge.get("type"))
        if key in seen_semantic:
            continue
        seen_semantic.add(key)
        if (edge.get("attributes") or {}).get("epistemic"):
            edge_kind = "epistemic"
        else:
            edge_kind = {
                "depends_on": "depends",
                "runtime_surface_of": "depends",
                "next": "depends",
                "implemented_by": "integrates",
                "implemented_in_repo": "integrates",
                "member_of": "integrates",
                "owned_by": "integrates",
                "has_stage": "integrates",
                "includes": "integrates",
                "produces_representation": "provides",
                "encoded_as": "integrates",
                "evidence_subject": "epistemic",
                "evidence_object": "epistemic",
                "requires_evidence": "epistemic",
                "verified_via": "epistemic",
            }.get(edge.get("type"), "default")
        connections.append({
            "from": src,
            "to": dst,
            "kind": edge_kind,
            "label": edge.get("type", "").replace("_", " "),
        })

    return {
        "meta": {
            "title": "z0archy",
            "author": "Zer0",
            "event": "live architecture",
            "date": "generated from kvnloo/z0",
            "source": "https://github.com/kvnloo/z0",
            "overview": {
                "title": "Whole Zer0 graph",
                "caption": "Semantic zoom compresses the world into logic first, then reveals concepts, important detail and source evidence as you move closer.",
            },
            "semanticZoom": {
                "levels": [
                    {"level": 1, "label": "logic"},
                    {"level": 2, "label": "concepts"},
                    {"level": 3, "label": "important detail"},
                    {"level": 4, "label": "deep detail"},
                    {"level": 5, "label": "source evidence"},
                ]
            },
        },
        "styling": {
            "canvas": {"background": "#FCFBF7", "fontFamily": "Helvetica, Arial, sans-serif", "monoFamily": "ui-monospace, 'SF Mono', Menlo, Consolas, monospace", "ink": "#1D1F23", "gray": "#62666F", "lgray": "#9BA0A8", "hair": "#E7E3D9"},
            "nodeStyles": {
                "default": {"background": "#FFFFFF", "borderColor": "#E7E3D9", "borderWidth": 1.5, "titleColor": "#1D1F23", "titleSize": 16, "subColor": "#62666F", "bodyColor": "#9BA0A8", "radius": 12, "padding": "10px 14px 11px", "shadow": True},
                "indigo": {"borderColor": "#574CE3", "titleColor": "#574CE3"},
                "runtime": {"borderColor": "#574CE3", "titleColor": "#574CE3"},
                "decision": {"borderColor": "#2D7DD2", "titleColor": "#2D7DD2"},
                "measurement": {"borderColor": "#A87B3E", "titleColor": "#A87B3E"},
                "environment": {"borderColor": "#5E9430", "titleColor": "#5E9430"},
                "compute": {"borderColor": "#8B5CF6", "titleColor": "#8B5CF6"},
                "research": {"borderColor": "#118A7E", "titleColor": "#118A7E"},
                "memory": {"borderColor": "#C05684", "titleColor": "#C05684"},
                "contract": {"borderColor": "#62666F", "titleColor": "#62666F", "background": "#F8F7F3"},
                "hub": {"titleSize": 22, "radius": 16, "padding": "15px 21px"},
                "mega": {"titleSize": 30, "padding": "18px 26px"},
                "tiny": {"titleSize": 12, "radius": 10, "padding": "8px 11px"},
            },
            "edgeStyles": {
                "default": {"stroke": "#D9D4C7", "width": 1.5, "labelColor": "#9BA0A8"},
                "depends": {"stroke": "#1D1F23", "width": 2.3, "labelColor": "#62666F"},
                "integrates": {"stroke": "#C9C4B8", "width": 1.2, "dash": "5 7", "labelColor": "#9BA0A8"},
                "provides": {"stroke": "#2D7DD2", "width": 1.4, "labelColor": "#2D7DD2"},
                "consumes": {"stroke": "#A87B3E", "width": 1.2, "dash": "3 6", "labelColor": "#A87B3E"},
                "epistemic": {"stroke": "#118A7E", "width": 1.5, "dash": "2 5", "labelColor": "#118A7E"},
            },
        },
        "layoutDefaults": {"floatAmp": 2.5, "fitMargin": 150, "pushMargin": 170, "zoomMax": 1.05},
        "slides": slides,
        "connections": connections,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default="generated/graph.json")
    parser.add_argument("--output", default="deck.json")
    args = parser.parse_args()
    graph_path = Path(args.graph)
    graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.exists() else None
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(graph), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")

if __name__ == "__main__":
    main()

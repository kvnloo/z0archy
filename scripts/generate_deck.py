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
        } for i, (name, spec) in enumerate(iface_items)],
        "layout": {"fitMargin": 160, "zoomMax": 0.86},
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

    return {
        "meta": {
            "title": "z0archy",
            "author": "Zer0",
            "event": "live architecture",
            "date": "generated from kvnloo/z0",
            "source": "https://github.com/kvnloo/z0",
            "overview": {
                "title": "Whole Zer0 graph",
                "caption": "Every registered component and contract in one spatial map. Use the arrow keys for guided plane-by-plane navigation.",
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

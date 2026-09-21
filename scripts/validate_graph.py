#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("graph", nargs="?", default="generated/graph.json")
    args = p.parse_args()
    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    assert graph.get("schemaVersion"), "schemaVersion required"
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    ids = {n["id"] for n in nodes}
    assert len(ids) == len(nodes), "duplicate graph node ids"
    for n in nodes:
        assert n.get("type") and n.get("label"), f"invalid node {n.get('id')}"
        assert n.get("provenance"), f"missing provenance: {n['id']}"
    for e in edges:
        assert e["source"] in ids, f"edge source missing: {e['source']}"
        assert e["target"] in ids, f"edge target missing: {e['target']}"
    print(f"ok: {len(nodes)} graph nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()

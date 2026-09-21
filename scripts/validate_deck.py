#!/usr/bin/env python3
"""Small structural validator for z0archy deck files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("deck", nargs="?", default="deck.json")
    args = parser.parse_args()

    data = json.loads(Path(args.deck).read_text(encoding="utf-8"))
    assert isinstance(data.get("slides"), list) and data["slides"], "slides must be non-empty"
    assert isinstance(data.get("connections"), list), "connections must be a list"

    ids = set()
    for slide in data["slides"]:
        assert "id" in slide and "anchor" in slide and "nodes" in slide
        for node in slide["nodes"]:
            nid = node["id"]
            assert nid not in ids, f"duplicate node id: {nid}"
            ids.add(nid)

    for edge in data["connections"]:
        assert edge["from"] in ids, f"edge source missing: {edge['from']}"
        assert edge["to"] in ids, f"edge target missing: {edge['to']}"

    for slide in data["slides"]:
        for nid in slide.get("include", []):
            assert nid in ids, f"included node missing: {nid}"

    print(f"ok: {len(ids)} nodes, {len(data['connections'])} connections, {len(data['slides'])} scenes")

if __name__ == "__main__":
    main()

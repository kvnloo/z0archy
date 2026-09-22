#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.hierarchy import propose_hierarchy_changes


def load_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def graph_identity(graph: dict) -> str:
    snapshot = graph.get("snapshot") or {}
    source = snapshot.get("source") or {}
    return json.dumps(
        {
            "source": source,
            "truthClass": snapshot.get("truthClass"),
            "nodeIds": sorted(n.get("id") for n in graph.get("nodes") or []),
            "edgeIds": sorted(e.get("id") for e in graph.get("edges") or []),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Propose conservative z0archy hierarchy changes from architecture history")
    p.add_argument("graph", nargs="?", default="generated/graph.json", help="current graph")
    p.add_argument("--history-dir", default="generated/history", help="directory of prior graph snapshots")
    p.add_argument("--history", action="append", default=[], help="additional historical snapshot; repeatable")
    p.add_argument("--output", default="generated/hierarchy-proposals.json")
    args = p.parse_args()

    current_path = Path(args.graph)
    current = load_graph(current_path)

    candidates: list[Path] = []
    history_dir = Path(args.history_dir)
    if history_dir.is_dir():
        candidates.extend(sorted(history_dir.glob("*.json"), key=lambda path: (path.stat().st_mtime_ns, path.name)))
    candidates.extend(Path(value) for value in args.history)

    snapshots: list[dict] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.is_file():
            continue
        graph = load_graph(path)
        ident = graph_identity(graph)
        if ident in seen:
            continue
        seen.add(ident)
        snapshots.append(graph)

    current_ident = graph_identity(current)
    snapshots = [graph for graph in snapshots if graph_identity(graph) != current_ident]
    snapshots.append(current)

    result = propose_hierarchy_changes(snapshots)
    result["inputs"] = {
        "current": str(current_path),
        "historyCount": max(0, len(snapshots) - 1),
        "historyDir": str(history_dir),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {output}: {result['summary']['proposalCount']} proposals "
        f"across {result['snapshotCount']} snapshots"
    )


if __name__ == "__main__":
    main()

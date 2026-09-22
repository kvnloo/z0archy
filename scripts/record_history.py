#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.history import export_history_snapshots, record_architecture_snapshot


def main() -> None:
    p = argparse.ArgumentParser(description="Record a z0archy graph as an ActiveGraph history run")
    p.add_argument("graph", nargs="?", default="generated/graph.json")
    p.add_argument("--store", default=".cache/activegraph-history.sqlite3")
    p.add_argument("--index", default="generated/history-index.json")
    p.add_argument("--history-dir", default="generated/history")
    args = p.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    result = record_architecture_snapshot(graph, args.store)
    index = export_history_snapshots(args.store, args.history_dir)
    index["latest"] = result

    target = Path(args.index)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    verb = "recorded" if result["created"] else "reused"
    print(
        f"{verb} {result['runId']}: {result['eventCount']} events; "
        f"{len(index['entries'])} historical architecture state(s)"
    )


if __name__ == "__main__":
    main()

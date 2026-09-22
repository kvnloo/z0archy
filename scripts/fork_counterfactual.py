#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.counterfactual import fork_counterfactual_world
from z0archy_core.history import export_history_snapshots


def main() -> None:
    p = argparse.ArgumentParser(
        description="Fork a recorded z0archy architecture world and apply a counterfactual graph"
    )
    p.add_argument("graph", help="counterfactual graph JSON, typically generated/virtual-graph.json")
    p.add_argument("--store", default=".cache/activegraph-history.sqlite3")
    p.add_argument("--parent-run")
    p.add_argument("--label")
    p.add_argument("--index", default="generated/history-index.json")
    p.add_argument("--history-dir", default="generated/history")
    args = p.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    result = fork_counterfactual_world(
        graph,
        args.store,
        parent_run_id=args.parent_run,
        label=args.label,
    )
    index = export_history_snapshots(args.store, args.history_dir)
    index["latestCounterfactual"] = result

    target = Path(args.index)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    verb = "forked" if result["created"] else "reused"
    print(
        f"{verb} {result['runId']} from {result['parentRunId']}: "
        f"{result['divergentObjects']} object divergence(s), "
        f"{result['divergentRelations']} relation divergence(s), "
        f"{result['sharedEvents']} shared event(s)"
    )


if __name__ == "__main__":
    main()

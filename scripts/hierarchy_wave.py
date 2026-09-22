#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.hierarchy import (
    analyze_hierarchy_wave,
    episodes_from_runtime_graph,
    merge_episode_documents,
)


def _read_json(path: str | Path) -> dict:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(
        description="Generate advisory slow hierarchy proposals from recurring episodes"
    )
    p.add_argument("--graph", default="generated/graph.json")
    p.add_argument("--episodes", action="append", default=[])
    p.add_argument("--runtime-evidence")
    p.add_argument("--min-support", type=int, default=3)
    p.add_argument("--output", default="generated/hierarchy-wave.json")
    args = p.parse_args()

    graph = _read_json(args.graph)
    documents = [_read_json(path) for path in args.episodes]
    if args.runtime_evidence:
        runtime_path = Path(args.runtime_evidence).expanduser()
        if runtime_path.is_file():
            documents.append(episodes_from_runtime_graph(_read_json(runtime_path)))
    episodes = merge_episode_documents(*documents)
    result = analyze_hierarchy_wave(
        graph,
        episodes,
        min_support=args.min_support,
    )
    result["episodeSources"] = {
        "files": [str(Path(path).expanduser()) for path in args.episodes],
        "runtimeEvidence": args.runtime_evidence,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    metrics = result["metrics"]
    print(
        f"hierarchy wave: {result['decision']} · {result['episodeCount']} episodes · "
        f"{metrics['mergeProposalCount']} merge · {metrics['splitProposalCount']} split · "
        f"{metrics['pruneProposalCount']} prune · {metrics['keepProposalCount']} keep"
    )


if __name__ == "__main__":
    main()

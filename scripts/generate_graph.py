#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from z0archy_core.graph import compile_graph
from z0archy_core.registry import load_registry


def main() -> None:
    p = argparse.ArgumentParser(description="Compile canonical z0 registry facts into z0archy graph IR")
    p.add_argument("--repo", default="kvnloo/z0")
    p.add_argument("--ref", default="main")
    p.add_argument("--z0-root", help="Read a local z0 checkout instead of GitHub")
    p.add_argument("--output", default="generated/graph.json")
    args = p.parse_args()
    docs = load_registry(repo=args.repo, ref=args.ref, local_root=args.z0_root)
    graph = compile_graph(
        docs["components"], docs["interfaces"], docs["profiles"], docs["maturity"],
        source_repo=args.repo, source_ref=args.ref,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")


if __name__ == "__main__":
    main()

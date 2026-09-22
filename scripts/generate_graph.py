#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.epistemic import apply_epistemic_registry
from z0archy_core.graph import compile_graph
from z0archy_core.registry import load_registry
from z0archy_core.suite import apply_suite_registry


def main() -> None:
    p = argparse.ArgumentParser(description="Compile canonical z0 registry facts into z0archy graph IR")
    p.add_argument("--repo", default="kvnloo/z0")
    p.add_argument("--ref", default="main")
    p.add_argument("--z0-root", help="Read a local z0 checkout instead of GitHub")
    p.add_argument("--output", default="generated/graph.json")
    args = p.parse_args()
    docs = load_registry(repo=args.repo, ref=args.ref, local_root=args.z0_root)
    graph = compile_graph(
        docs["components"],
        docs["interfaces"],
        docs["profiles"],
        docs["maturity"],
        docs.get("harnesses"),
        docs.get("mechanisms"),
        docs.get("lifecycles"),
        source_repo=args.repo,
        source_ref=args.ref,
    )
    graph = apply_epistemic_registry(
        graph,
        docs.get("representations"),
        docs.get("evidence_dependencies"),
        source_repo=args.repo,
        source_ref=args.ref,
    )
    graph = apply_suite_registry(
        graph,
        docs.get("suite"),
        source_repo=args.repo,
        source_ref=args.ref,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        old = json.loads(out.read_text(encoding="utf-8"))
        old_cmp = json.loads(json.dumps(old))
        new_cmp = json.loads(json.dumps(graph))
        (old_cmp.get("snapshot") or {}).pop("generatedAt", None)
        (new_cmp.get("snapshot") or {}).pop("generatedAt", None)
        if old_cmp == new_cmp:
            graph["snapshot"]["generatedAt"] = old.get("snapshot", {}).get("generatedAt")
    out.write_text(json.dumps(graph, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")


if __name__ == "__main__":
    main()

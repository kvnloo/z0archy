#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.sources import GitHubRawSource, LocalGitSource
from z0archy_core.virtual import compile_virtual_snapshot


def _pairs(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in values:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise SystemExit(f"expected REPO=VALUE, got {item!r}")
        out[key] = value
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Compile a virtual multi-repo z0 architecture snapshot")
    p.add_argument("--base", default="generated/graph.json")
    p.add_argument("--selection", required=True, help="JSON selection manifest")
    p.add_argument("--github-index", default="generated/github-index.json")
    p.add_argument("--local-root", action="append", default=[], metavar="REPO=PATH")
    p.add_argument("--output", default="generated/virtual-graph.json")
    args = p.parse_args()

    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    selection = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    local_roots = _pairs(args.local_root)

    providers = {"github": GitHubRawSource()}
    if local_roots:
        providers["local"] = LocalGitSource(local_roots)

    resolved: dict[str, str] = {}
    index_path = Path(args.github_index)
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for repo, spec in (selection.get("repos") or {}).items():
            if spec.get("source", "github") != "github":
                continue
            ref = spec.get("ref", "HEAD")
            row = (index.get("repositories") or {}).get(repo) or {}
            for branch in row.get("branches") or []:
                if branch.get("name") == ref and branch.get("oid"):
                    resolved[repo] = branch["oid"]
                    break

    graph = compile_virtual_snapshot(base, selection, providers, resolved_refs=resolved)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {out}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
        f"{len(selection.get('repos') or {})} selected repos"
    )


if __name__ == "__main__":
    main()

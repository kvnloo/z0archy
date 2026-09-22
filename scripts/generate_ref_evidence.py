#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.introspection import inspect_repository
from z0archy_core.sources import GitHubRawSource


def evidence_path(root: Path, repo: str, key: str) -> Path:
    owner, name = repo.split("/", 1)
    return root / owner / name / f"{key}.json"


def main() -> None:
    p = argparse.ArgumentParser(
        description="Materialize branch evidence packs keyed by immutable Git commit SHA"
    )
    p.add_argument("--index", default="generated/github-index.json")
    p.add_argument("--output-dir", default="generated/ref-evidence")
    p.add_argument("--cache-dir", default=".cache/ref-evidence")
    args = p.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    out_root = Path(args.output_dir)
    cache_root = Path(args.cache_dir)
    source = GitHubRawSource()

    built = reused = failed = 0
    seen: set[tuple[str, str]] = set()
    for repo, meta in sorted((index.get("repositories") or {}).items()):
        for branch in meta.get("branches") or []:
            oid = branch.get("oid")
            if not oid or (repo, oid) in seen:
                continue
            seen.add((repo, oid))
            cache_path = evidence_path(cache_root, repo, oid)
            out_path = evidence_path(out_root, repo, oid)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if cache_path.is_file():
                shutil.copyfile(cache_path, out_path)
                reused += 1
                continue

            try:
                # Read by immutable SHA even though the index row came from a branch.
                pack = inspect_repository(source, repo, oid, resolved_ref=oid)
                pack["branchHints"] = [
                    b.get("name")
                    for b in meta.get("branches") or []
                    if b.get("oid") == oid and b.get("name")
                ]
            except Exception as exc:
                pack = {
                    "repo": repo,
                    "ref": oid,
                    "resolvedRef": oid,
                    "nodes": [],
                    "edges": [],
                    "summary": {},
                    "error": f"{type(exc).__name__}: {exc}",
                }
                failed += 1

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
            shutil.copyfile(cache_path, out_path)
            built += 1

    print(
        f"ref evidence: {built} built, {reused} cache hits, {failed} failed, "
        f"{len(seen)} unique repo commits"
    )


if __name__ == "__main__":
    main()

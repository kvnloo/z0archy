#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.introspection import inspect_repository
from z0archy_core.local_git import build_local_snapshot_from_git_roots, discover_git_roots
from z0archy_core.sources import LocalGitSource


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _evidence_path(root: Path, repo: str, key: str) -> Path:
    owner, name = repo.split("/", 1)
    return root / owner / name / f"{key}.json"


def refresh(
    git_roots: list[Path],
    output: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    snapshot = build_local_snapshot_from_git_roots(git_roots)
    _atomic_json(output, snapshot)

    for repo, meta in snapshot["repositories"].items():
        if "/" not in repo:
            continue
        for worktree in meta.get("worktrees") or []:
            path = worktree.get("path")
            key = worktree.get("evidenceKey")
            if not path or not key:
                continue
            provider = LocalGitSource({repo: path})
            try:
                pack = inspect_repository(
                    provider,
                    repo,
                    "WORKTREE",
                    resolved_ref=key,
                )
                pack["worktree"] = {
                    "path": path,
                    "branch": worktree.get("branch"),
                    "head": worktree.get("head"),
                    "dirtyFiles": worktree.get("dirtyFiles", 0),
                    "ahead": worktree.get("ahead", 0),
                    "behind": worktree.get("behind", 0),
                }
                _atomic_json(_evidence_path(evidence_root, repo, key), pack)
            except Exception as exc:
                _atomic_json(
                    _evidence_path(evidence_root, repo, key),
                    {
                        "repo": repo,
                        "ref": "WORKTREE",
                        "resolvedRef": key,
                        "nodes": [],
                        "edges": [],
                        "summary": {},
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
    return snapshot


def main() -> None:
    p = argparse.ArgumentParser(description="Serve z0archy with a live read-only local Git overlay")
    p.add_argument("--workspace", action="append", required=True, help="workspace root to scan; repeatable")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--rediscover-interval", type=float, default=30.0)
    p.add_argument("--output", default="generated/local-state.json")
    p.add_argument("--evidence-dir", default="generated/ref-evidence")
    args = p.parse_args()

    output = Path(args.output)
    evidence_root = Path(args.evidence_dir)
    git_roots = discover_git_roots(args.workspace)
    refresh(git_roots, output, evidence_root)

    stop = threading.Event()

    def watch() -> None:
        roots = list(git_roots)
        last_discovery = time.monotonic()
        while not stop.wait(args.interval):
            try:
                now = time.monotonic()
                if now - last_discovery >= args.rediscover_interval:
                    roots = discover_git_roots(args.workspace)
                    last_discovery = now
                refresh(roots, output, evidence_root)
            except Exception as exc:
                print(f"local scan failed: {exc}")

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    server = ThreadingHTTPServer((args.host, args.port), SimpleHTTPRequestHandler)
    print(
        f"z0archy: http://{args.host}:{args.port} "
        f"(watching {len(git_roots)} repos under {', '.join(args.workspace)})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()

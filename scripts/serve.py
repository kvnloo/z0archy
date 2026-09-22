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

from z0archy_core.hierarchy import analyze_hierarchy_wave, episodes_from_runtime_graph, merge_episode_documents
from z0archy_core.introspection import inspect_repository
from z0archy_core.local_git import build_local_snapshot_from_git_roots, discover_git_roots
from z0archy_core.runtime_evidence import compile_runtime_evidence, runtime_input_fingerprint
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
            evidence_path = _evidence_path(evidence_root, repo, key)
            if evidence_path.is_file():
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
                _atomic_json(evidence_path, pack)
            except Exception as exc:
                _atomic_json(
                    evidence_path,
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


def _refresh_runtime(
    *,
    tokenomics_paths: list[str],
    agenttrace_paths: list[str],
    aodl_paths: list[str],
    output: Path,
    state: dict[str, str | None],
) -> None:
    all_paths = [*tokenomics_paths, *agenttrace_paths, *aodl_paths]
    if not all_paths:
        if output.exists():
            output.unlink()
        state["fingerprint"] = None
        return
    fingerprint = runtime_input_fingerprint(all_paths)
    if fingerprint == state.get("fingerprint") and output.is_file():
        return
    graph = compile_runtime_evidence(
        tokenomics_paths=tokenomics_paths,
        agenttrace_paths=agenttrace_paths,
        aodl_paths=aodl_paths,
    )
    _atomic_json(output, graph)
    state["fingerprint"] = fingerprint


def _refresh_hierarchy(
    *,
    graph_path: Path,
    episode_paths: list[str],
    runtime_path: Path,
    output: Path,
    state: dict[str, str | None],
) -> None:
    if not graph_path.is_file():
        return
    tracked = [str(graph_path), *episode_paths]
    if runtime_path.is_file():
        tracked.append(str(runtime_path))
    fingerprint = runtime_input_fingerprint(tracked)
    if fingerprint == state.get("fingerprint") and output.is_file():
        return

    documents: list[dict[str, Any]] = []
    source_errors: list[dict[str, str]] = []
    for raw in episode_paths:
        path = Path(raw).expanduser()
        if not path.is_file():
            source_errors.append({"path": str(path), "error": "missing"})
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            source_errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        if isinstance(value, dict):
            documents.append(value)

    if runtime_path.is_file():
        try:
            runtime_graph = json.loads(runtime_path.read_text(encoding="utf-8"))
            if isinstance(runtime_graph, dict):
                documents.append(episodes_from_runtime_graph(runtime_graph))
        except (OSError, json.JSONDecodeError) as exc:
            source_errors.append({"path": str(runtime_path), "error": f"{type(exc).__name__}: {exc}"})

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    episodes = merge_episode_documents(*documents)
    result = analyze_hierarchy_wave(graph, episodes)
    result["episodeSources"] = {
        "files": [str(Path(path).expanduser()) for path in episode_paths],
        "runtimeEvidence": str(runtime_path) if runtime_path.is_file() else None,
        "errors": source_errors,
    }
    _atomic_json(output, result)
    state["fingerprint"] = fingerprint


def main() -> None:
    p = argparse.ArgumentParser(description="Serve z0archy with live read-only Git and runtime overlays")
    p.add_argument("--workspace", action="append", required=True, help="workspace root to scan; repeatable")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--rediscover-interval", type=float, default=30.0)
    p.add_argument("--output", default="generated/local-state.json")
    p.add_argument("--evidence-dir", default="generated/ref-evidence")
    p.add_argument("--runtime-output", default="generated/runtime-evidence.json")
    p.add_argument("--tokenomics-events", action="append", default=[])
    p.add_argument("--agenttrace-report", action="append", default=[])
    p.add_argument("--aodl-document", action="append", default=[])
    p.add_argument("--hierarchy-episodes", action="append", default=[])
    p.add_argument("--hierarchy-output", default="generated/hierarchy-wave.json")
    p.add_argument("--graph", default="generated/graph.json")
    args = p.parse_args()

    output = Path(args.output)
    evidence_root = Path(args.evidence_dir)
    runtime_output = Path(args.runtime_output)
    tokenomics_paths = list(args.tokenomics_events)
    if not tokenomics_paths:
        candidate = Path("~/.local/share/tokenomics/events.jsonl").expanduser()
        if candidate.is_file():
            tokenomics_paths.append(str(candidate))
    runtime_state: dict[str, str | None] = {"fingerprint": None}
    hierarchy_state: dict[str, str | None] = {"fingerprint": None}
    hierarchy_output = Path(args.hierarchy_output)
    graph_path = Path(args.graph)

    git_roots = discover_git_roots(args.workspace)
    refresh(git_roots, output, evidence_root)
    _refresh_runtime(
        tokenomics_paths=tokenomics_paths,
        agenttrace_paths=args.agenttrace_report,
        aodl_paths=args.aodl_document,
        output=runtime_output,
        state=runtime_state,
    )
    _refresh_hierarchy(
        graph_path=graph_path,
        episode_paths=args.hierarchy_episodes,
        runtime_path=runtime_output,
        output=hierarchy_output,
        state=hierarchy_state,
    )

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
                _refresh_runtime(
                    tokenomics_paths=tokenomics_paths,
                    agenttrace_paths=args.agenttrace_report,
                    aodl_paths=args.aodl_document,
                    output=runtime_output,
                    state=runtime_state,
                )
                _refresh_hierarchy(
                    graph_path=graph_path,
                    episode_paths=args.hierarchy_episodes,
                    runtime_path=runtime_output,
                    output=hierarchy_output,
                    state=hierarchy_state,
                )
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

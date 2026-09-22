#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.introspection import inspect_repository
from z0archy_core.sources import GitHubRawSource

_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def evidence_path(root: Path, repo: str, key: str) -> Path:
    owner, name = repo.split("/", 1)
    return root / owner / name / f"{key}.json"


def canonical_pins(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    pins: dict[str, list[dict[str, Any]]] = {}
    for node in graph.get("nodes") or []:
        if node.get("type") != "component":
            continue
        attrs = node.get("attributes") or {}
        repo = attrs.get("repo")
        install = attrs.get("install") or {}
        ref = install.get("ref")
        if not repo or not ref:
            continue
        pins.setdefault(str(repo), []).append({
            "component": attrs.get("component_id") or node.get("label"),
            "branch": install.get("branch"),
            "ref": str(ref),
            "declaredBy": node.get("id"),
        })
    return pins


def main() -> None:
    p = argparse.ArgumentParser(
        description="Materialize branch + canonical-pin evidence keyed by immutable Git SHA"
    )
    p.add_argument("--index", default="generated/github-index.json")
    p.add_argument("--graph", default="generated/graph.json")
    p.add_argument("--canonical-index", default="generated/canonical-ref-index.json")
    p.add_argument("--output-dir", default="generated/ref-evidence")
    p.add_argument("--cache-dir", default=".cache/ref-evidence")
    args = p.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    graph_path = Path(args.graph)
    graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.is_file() else {"nodes": []}
    pin_map = canonical_pins(graph)

    out_root = Path(args.output_dir)
    cache_root = Path(args.cache_dir)
    source = GitHubRawSource()

    targets: dict[str, dict[str, dict[str, Any]]] = {}
    for repo, meta in sorted((index.get("repositories") or {}).items()):
        repo_targets = targets.setdefault(repo, {})
        for branch in meta.get("branches") or []:
            oid = branch.get("oid")
            if not oid:
                continue
            row = repo_targets.setdefault(str(oid), {"branchHints": [], "canonicalPins": []})
            if branch.get("name") and branch["name"] not in row["branchHints"]:
                row["branchHints"].append(branch["name"])

    canonical_index: dict[str, Any] = {"version": 1, "repos": {}}
    for repo, pins in sorted(pin_map.items()):
        repo_row = canonical_index["repos"].setdefault(repo, {"pins": []})
        for pin in pins:
            ref = pin["ref"]
            evidence_key = ref if _SHA.match(ref) else None
            if evidence_key is None:
                # Central z0 currently uses commit SHAs for component pins.
                # Keep non-SHA declarations explicit instead of pretending a branch
                # head is equivalent to the declared canonical identity.
                repo_row["pins"].append({**pin, "evidenceKey": None, "resolved": False})
                continue
            target = targets.setdefault(repo, {}).setdefault(
                evidence_key, {"branchHints": [], "canonicalPins": []}
            )
            target["canonicalPins"].append(pin)
            repo_row["pins"].append({**pin, "evidenceKey": evidence_key, "resolved": True})

    # Also expose unpinned repos seen by the GitHub index. The browser can choose
    # their default branch while clearly labeling it as observational fallback.
    for repo, meta in sorted((index.get("repositories") or {}).items()):
        repo_row = canonical_index["repos"].setdefault(repo, {"pins": []})
        repo_row["defaultBranch"] = meta.get("defaultBranch")
        repo_row["defaultHead"] = meta.get("defaultHead")
        repo_row["canonical"] = bool(repo_row["pins"])

    built = reused = failed = 0
    seen: set[tuple[str, str]] = set()
    for repo, commits in sorted(targets.items()):
        for oid, hints in sorted(commits.items()):
            if (repo, oid) in seen:
                continue
            seen.add((repo, oid))
            cache_path = evidence_path(cache_root, repo, oid)
            out_path = evidence_path(out_root, repo, oid)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if cache_path.is_file():
                pack = json.loads(cache_path.read_text(encoding="utf-8"))
                reused += 1
            else:
                try:
                    # Read by immutable SHA even when target discovery came from a branch.
                    pack = inspect_repository(source, repo, oid, resolved_ref=oid)
                    built += 1
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
                    built += 1

            pack["branchHints"] = sorted(hints.get("branchHints") or [])
            pack["canonicalPins"] = hints.get("canonicalPins") or []
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
            shutil.copyfile(cache_path, out_path)

    canonical_path = Path(args.canonical_index)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text(json.dumps(canonical_index, indent=2) + "\n", encoding="utf-8")

    print(
        f"ref evidence: {built} built, {reused} cache hits, {failed} failed, "
        f"{len(seen)} unique repo commits, {sum(len(v['pins']) for v in canonical_index['repos'].values())} canonical pin(s)"
    )


if __name__ == "__main__":
    main()

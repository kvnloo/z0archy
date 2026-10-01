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
            "status": attrs.get("status"),
            "kind": attrs.get("kind"),
            "declaredBy": node.get("id"),
        })
    return pins


def _add_target(
    targets: dict[str, dict[str, dict[str, Any]]],
    repo: str,
    oid: str | None,
    *,
    branch_hint: str | None = None,
) -> None:
    if not oid:
        return
    row = targets.setdefault(repo, {}).setdefault(
        str(oid), {"branchHints": [], "canonicalPins": []}
    )
    if branch_hint and branch_hint not in row["branchHints"]:
        row["branchHints"].append(branch_hint)


def bounded_branch_targets(
    index: dict[str, Any],
    *,
    branch_limit_per_repo: int = 4,
    selection_docs: list[tuple[str, dict[str, Any]]] | None = None,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, str]]]:
    """Choose a bounded hosted evidence set.

    Full implementation evidence is materialized for default heads, a small recent
    branch window, and every ref named by a checked-in selection preset. Canonical
    component pins are added separately and are never subject to this bound.
    """
    targets: dict[str, dict[str, dict[str, Any]]] = {}
    repositories = index.get("repositories") or {}

    for repo, meta in sorted(repositories.items()):
        _add_target(
            targets,
            repo,
            meta.get("defaultHead"),
            branch_hint=meta.get("defaultBranch"),
        )
        branches = list(meta.get("branches") or [])
        limit = max(0, branch_limit_per_repo)
        for branch in branches[:limit]:
            _add_target(
                targets,
                repo,
                branch.get("oid"),
                branch_hint=branch.get("name"),
            )

    unresolved: list[dict[str, str]] = []
    for source_name, doc in selection_docs or []:
        for repo, spec in sorted((doc.get("repos") or {}).items()):
            if not isinstance(spec, dict) or spec.get("source", "github") != "github":
                continue
            ref = str(spec.get("ref") or "")
            if not ref:
                continue
            if _SHA.match(ref):
                _add_target(targets, repo, ref, branch_hint=ref)
                continue
            meta = repositories.get(repo) or {}
            match = next(
                (
                    branch for branch in (meta.get("branches") or [])
                    if branch.get("name") == ref and branch.get("oid")
                ),
                None,
            )
            if match:
                _add_target(
                    targets,
                    repo,
                    match.get("oid"),
                    branch_hint=match.get("name"),
                )
                continue
            if meta.get("defaultBranch") == ref and meta.get("defaultHead"):
                _add_target(
                    targets,
                    repo,
                    meta.get("defaultHead"),
                    branch_hint=ref,
                )
                continue
            unresolved.append({
                "selection": source_name,
                "repo": repo,
                "ref": ref,
            })
    return targets, unresolved


def load_selection_docs(selection_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    if not selection_dir.is_dir():
        return []
    docs: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(selection_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            docs.append((path.name, doc))
    return docs


def structural_manifest_path(pack: dict[str, Any]) -> str | None:
    """Return the explicit implementation-manifest path carried by an evidence pack."""
    for node in pack.get("nodes") or []:
        if node.get("type") != "implementation_manifest":
            continue
        path = str((node.get("attributes") or {}).get("manifestPath") or "")
        if path in {"zer0.repo.yaml", "zer0.component.yaml"}:
            return path
    return None


def manifest_coverage(index: dict[str, Any]) -> dict[str, Any]:
    """Summarize exact-pin structural coverage without treating idea-stage gaps as failures."""
    rows: list[dict[str, Any]] = []
    for repo, meta in sorted((index.get("repos") or {}).items()):
        for pin in meta.get("pins") or []:
            expected = pin.get("status") not in {"idea", "retired"}
            rows.append({
                "repo": repo,
                "component": pin.get("component"),
                "ref": pin.get("ref"),
                "status": pin.get("status"),
                "expected": expected,
                "resolved": bool(pin.get("resolved")),
                "manifestPath": pin.get("manifestPath"),
                "structuralManifest": bool(pin.get("structuralManifest")),
            })
    expected_rows = [row for row in rows if row["expected"]]
    missing_expected = [
        row for row in expected_rows
        if row["resolved"] and not row["structuralManifest"]
    ]
    unresolved_expected = [row for row in expected_rows if not row["resolved"]]
    return {
        "totalPins": len(rows),
        "withStructuralManifest": sum(1 for row in rows if row["structuralManifest"]),
        "expectedPins": len(expected_rows),
        "expectedWithStructuralManifest": sum(
            1 for row in expected_rows if row["structuralManifest"]
        ),
        "missingExpected": missing_expected,
        "unresolvedExpected": unresolved_expected,
        "rows": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description="Materialize branch + canonical-pin evidence keyed by immutable Git SHA"
    )
    p.add_argument("--index", default="generated/github-index.json")
    p.add_argument("--graph", default="generated/graph.json")
    p.add_argument("--canonical-index", default="generated/canonical-ref-index.json")
    p.add_argument("--output-dir", default="generated/ref-evidence")
    p.add_argument("--cache-dir", default=".cache/ref-evidence")
    p.add_argument("--selection-dir", default="selections")
    p.add_argument(
        "--branch-limit-per-repo",
        type=int,
        default=4,
        help="recent branch heads to prebuild per repo in addition to default, canonical pins, and selection presets",
    )
    args = p.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    graph_path = Path(args.graph)
    graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.is_file() else {"nodes": []}
    pin_map = canonical_pins(graph)

    out_root = Path(args.output_dir)
    cache_root = Path(args.cache_dir)
    source = GitHubRawSource()

    selection_docs = load_selection_docs(Path(args.selection_dir))
    targets, unresolved_selection_targets = bounded_branch_targets(
        index,
        branch_limit_per_repo=args.branch_limit_per_repo,
        selection_docs=selection_docs,
    )

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
            _add_target(
                targets,
                repo,
                evidence_key,
                branch_hint=str(pin.get("branch") or "") or None,
            )
            targets[repo][evidence_key]["canonicalPins"].append(pin)
            repo_row["pins"].append({**pin, "evidenceKey": evidence_key, "resolved": True})

    # Also expose unpinned repos seen by the GitHub index. The browser can choose
    # their default branch while clearly labeling it as observational fallback.
    for repo, meta in sorted((index.get("repositories") or {}).items()):
        repo_row = canonical_index["repos"].setdefault(repo, {"pins": []})
        repo_row["defaultBranch"] = meta.get("defaultBranch")
        repo_row["defaultHead"] = meta.get("defaultHead")
        repo_row["canonical"] = bool(repo_row["pins"])
        repo_row["materializedEvidenceKeys"] = sorted(targets.get(repo, {}))

    canonical_index["evidenceMaterialization"] = {
        "policy": "canonical + default + recent-window + checked-in selections",
        "branchLimitPerRepo": args.branch_limit_per_repo,
        "selectionFiles": [name for name, _ in selection_docs],
        "unresolvedSelectionTargets": unresolved_selection_targets,
        "targetRepoCount": len(targets),
        "targetCommitCount": sum(len(commits) for commits in targets.values()),
    }

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

            manifest_path = structural_manifest_path(pack)
            repo_row = canonical_index["repos"].setdefault(repo, {"pins": []})
            for pin in repo_row.get("pins") or []:
                if pin.get("evidenceKey") != oid:
                    continue
                pin["manifestPath"] = manifest_path
                pin["structuralManifest"] = bool(manifest_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
            shutil.copyfile(cache_path, out_path)

    canonical_index["manifestCoverage"] = manifest_coverage(canonical_index)

    canonical_path = Path(args.canonical_index)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text(json.dumps(canonical_index, indent=2) + "\n", encoding="utf-8")

    print(
        f"ref evidence: {built} built, {reused} cache hits, {failed} failed, "
        f"{len(seen)} unique repo commits, {sum(len(v['pins']) for v in canonical_index['repos'].values())} canonical pin(s), "
        f"{canonical_index['manifestCoverage']['expectedWithStructuralManifest']}/"
        f"{canonical_index['manifestCoverage']['expectedPins']} expected pin(s) structurally manifest-backed"
    )


if __name__ == "__main__":
    main()

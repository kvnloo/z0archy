from __future__ import annotations

import json
import re
from typing import Any

import yaml

from .evidence import attach_evidence_dependencies
from .graph import zid
from .sources import SourceProvider, content_sha256

PROBE_PATHS = (
    "zer0.component.yaml",
    "ARCHITECTURE.md",
    "README.md",
    "AGENTS.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
)


def inspect_repository(
    provider: SourceProvider,
    repo: str,
    ref: str,
    *,
    resolved_ref: str | None = None,
) -> dict[str, Any]:
    """Compile bounded implementation evidence from one exact repository ref.

    This intentionally probes a small, explicit surface. It does not infer architecture
    from arbitrary code imports yet; future analyzers can append evidence without changing
    the selection/ref identity contract.
    """
    resolved = resolved_ref or provider.resolve_ref(repo, ref)
    repo_ref_id = zid("repo-ref", f"{repo}@{resolved}")
    nodes: list[dict[str, Any]] = [{
        "id": repo_ref_id,
        "type": "repo_ref",
        "label": f"{repo}@{ref}",
        "attributes": {
            "repo": repo,
            "ref": ref,
            "resolvedRef": resolved,
            "source": provider.kind,
        },
        "provenance": [{
            "class": "implemented",
            "source": repo,
            "ref": resolved,
            "path": ".git",
            "field": "ref",
        }],
    }]
    edges: list[dict[str, Any]] = [{
        "id": zid("edge", f"has_ref:{repo}->{resolved}"),
        "type": "has_ref",
        "source": zid("repo", repo),
        "target": repo_ref_id,
        "provenance": [{
            "class": "implemented",
            "source": repo,
            "ref": resolved,
            "path": ".git",
            "field": "ref",
        }],
    }]

    read_ref = resolved if provider.kind == "github" and not resolved.startswith("github:") else ref

    docs: dict[str, str] = {}
    for path in PROBE_PATHS:
        text = provider.read_text(repo, read_ref, path)
        if text is None:
            continue
        docs[path] = text
        artifact_id = zid("artifact", f"{repo}@{resolved}:{path}")
        nodes.append({
            "id": artifact_id,
            "type": "source_artifact",
            "label": path,
            "attributes": {
                "repo": repo,
                "ref": ref,
                "path": path,
                "sha256": content_sha256(text),
                "bytes": len(text.encode("utf-8")),
                "role": _artifact_role(path),
            },
            "provenance": [{
                "class": "implemented",
                "source": repo,
                "ref": resolved,
                "path": path,
                "field": "content",
            }],
        })
        edges.append({
            "id": zid("edge", f"contains:{resolved}:{path}"),
            "type": "contains",
            "source": repo_ref_id,
            "target": artifact_id,
            "provenance": [{
                "class": "implemented",
                "source": repo,
                "ref": resolved,
                "path": path,
                "field": "existence",
            }],
        })

    manifest = _parse_manifest(docs.get("zer0.component.yaml"))
    package = _package_identity(docs)
    if manifest:
        mid = zid("implementation-manifest", f"{repo}@{resolved}")
        nodes.append({
            "id": mid,
            "type": "implementation_manifest",
            "label": manifest.get("name") or manifest.get("id") or repo,
            "attributes": manifest,
            "provenance": [{
                "class": "implemented",
                "source": repo,
                "ref": resolved,
                "path": "zer0.component.yaml",
                "field": "document",
            }],
        })
        edges.append({
            "id": zid("edge", f"declares:{resolved}:manifest"),
            "type": "declares",
            "source": repo_ref_id,
            "target": mid,
            "provenance": nodes[-1]["provenance"],
        })

    if package:
        pid = zid("package", f"{repo}:{package['name']}")
        nodes.append({
            "id": pid,
            "type": "package",
            "label": package["name"],
            "attributes": {"repo": repo, **package},
            "provenance": [{
                "class": "implemented",
                "source": repo,
                "ref": resolved,
                "path": package["sourcePath"],
                "field": "package",
            }],
        })
        edges.append({
            "id": zid("edge", f"contains_package:{resolved}:{package['name']}"),
            "type": "contains_package",
            "source": repo_ref_id,
            "target": pid,
            "provenance": nodes[-1]["provenance"],
        })

    attach_evidence_dependencies(edges, verified_at=None)

    return {
        "repo": repo,
        "ref": ref,
        "resolvedRef": resolved,
        "nodes": nodes,
        "edges": edges,
        "summary": _summarize_docs(docs),
    }


def _parse_manifest(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    doc = yaml.safe_load(text)
    return doc if isinstance(doc, dict) else None


def _package_identity(docs: dict[str, str]) -> dict[str, Any] | None:
    if "package.json" in docs:
        try:
            data = json.loads(docs["package.json"])
        except json.JSONDecodeError:
            data = {}
        name = data.get("name")
        if name:
            return {
                "name": str(name),
                "version": data.get("version"),
                "ecosystem": "npm",
                "sourcePath": "package.json",
            }

    if "pyproject.toml" in docs:
        text = docs["pyproject.toml"]
        match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', text, flags=re.MULTILINE)
        if match:
            return {
                "name": match.group(1),
                "ecosystem": "python",
                "sourcePath": "pyproject.toml",
            }

    if "Cargo.toml" in docs:
        text = docs["Cargo.toml"]
        match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', text, flags=re.MULTILINE)
        if match:
            return {
                "name": match.group(1),
                "ecosystem": "cargo",
                "sourcePath": "Cargo.toml",
            }
    return None


def _artifact_role(path: str) -> str:
    if path == "zer0.component.yaml":
        return "manifest"
    if path == "ARCHITECTURE.md":
        return "architecture"
    if path == "README.md":
        return "readme"
    if path == "AGENTS.md":
        return "agent_instructions"
    return "package_metadata"


def _summarize_docs(docs: dict[str, str]) -> dict[str, Any]:
    return {
        "hasManifest": "zer0.component.yaml" in docs,
        "hasArchitecture": "ARCHITECTURE.md" in docs,
        "hasReadme": "README.md" in docs,
        "hasAgentInstructions": "AGENTS.md" in docs,
        "packageMetadata": [
            p for p in ("package.json", "pyproject.toml", "Cargo.toml") if p in docs
        ],
    }

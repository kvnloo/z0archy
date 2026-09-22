from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import PurePosixPath
from typing import Any

import yaml

from .graph import zid
from .sources import SourceProvider, content_sha256

ROOT_PROBE_PATHS = (
    "zer0.component.yaml",
    "ARCHITECTURE.md",
    "README.md",
    "AGENTS.md",
    "SYSTEM.md",
    "CONTRACT.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
)

PACKAGE_BASENAMES = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod"}
ARCH_DOC_BASENAMES = {"ARCHITECTURE.md", "README.md", "AGENTS.md", "SYSTEM.md", "CONTRACT.md"}
IGNORED_SEGMENTS = {
    ".git", "node_modules", ".venv", "venv", "vendor", "dist", "build", ".cache",
    "target", "coverage", ".next", ".turbo", "__pycache__", "site-packages",
}
MAX_PACKAGE_MANIFESTS = 96
MAX_SCHEMA_ARTIFACTS = 96
MAX_WORKFLOW_ARTIFACTS = 48
MAX_ARCH_DOCS = 48
MAX_TEST_SAMPLES = 32


def inspect_repository(
    provider: SourceProvider,
    repo: str,
    ref: str,
    *,
    resolved_ref: str | None = None,
) -> dict[str, Any]:
    """Compile loss-aware implementation evidence from one exact repository ref.

    The tree is inventoried once, but only architecture-bearing facts are materialized:
    packages, architecture docs, schemas, workflows, tests and a compressed structure
    summary. This preserves reconstructability without mirroring every source file into
    the semantic graph.
    """
    resolved = resolved_ref or provider.resolve_ref(repo, ref)
    repo_ref_id = zid("repo-ref", f"{repo}@{resolved}")
    node_map: dict[str, dict[str, Any]] = {}
    edge_map: dict[str, dict[str, Any]] = {}

    def prov(path: str, field: str = "content") -> list[dict[str, Any]]:
        return [{
            "class": "implemented",
            "source": repo,
            "ref": resolved,
            "path": path,
            "field": field,
        }]

    def add_node(node: dict[str, Any]) -> None:
        existing = node_map.get(node["id"])
        if existing:
            existing_prov = existing.setdefault("provenance", [])
            for row in node.get("provenance") or []:
                if row not in existing_prov:
                    existing_prov.append(row)
            return
        node_map[node["id"]] = node

    def add_edge(
        kind: str,
        source: str,
        target: str,
        key: str,
        *,
        path: str,
        field: str,
    ) -> None:
        edge_id = zid("edge", f"{kind}:{key}")
        edge_map[edge_id] = {
            "id": edge_id,
            "type": kind,
            "source": source,
            "target": target,
            "provenance": prov(path, field),
        }

    add_node({
        "id": repo_ref_id,
        "type": "repo_ref",
        "label": f"{repo}@{ref}",
        "attributes": {
            "repo": repo,
            "ref": ref,
            "resolvedRef": resolved,
            "source": provider.kind,
        },
        "provenance": prov(".git", "ref"),
    })
    add_edge(
        "has_ref", zid("repo", repo), repo_ref_id, f"{repo}->{resolved}",
        path=".git", field="ref",
    )

    read_ref = resolved if provider.kind == "github" and not resolved.startswith("github:") else ref
    tree_error: str | None = None
    try:
        tree = provider.list_tree(repo, read_ref)
    except Exception as exc:  # bounded root probing remains useful if tree enumeration fails
        tree = {"entries": [], "truncated": False}
        tree_error = f"{type(exc).__name__}: {exc}"

    entries = [
        row for row in (tree.get("entries") or [])
        if row.get("type") == "blob" and row.get("path") and not _ignored_path(str(row["path"]))
    ]
    entries.sort(key=lambda row: str(row["path"]))
    by_path = {str(row["path"]): row for row in entries}
    content_cache: dict[str, str | None] = {}

    def read(path: str) -> str | None:
        if path not in content_cache:
            content_cache[path] = provider.read_text(repo, read_ref, path)
        return content_cache[path]

    def add_artifact(path: str, role: str, *, text: str | None = None) -> str:
        row = by_path.get(path) or {}
        if text is None and path in content_cache:
            text = content_cache[path]
        attrs: dict[str, Any] = {
            "repo": repo,
            "ref": ref,
            "path": path,
            "role": role,
            "bytes": len(text.encode("utf-8")) if text is not None else row.get("size"),
            "gitBlobOid": row.get("oid"),
        }
        if text is not None:
            attrs["sha256"] = content_sha256(text)
        artifact_id = zid("artifact", f"{repo}@{resolved}:{path}")
        add_node({
            "id": artifact_id,
            "type": "source_artifact",
            "label": path,
            "attributes": attrs,
            "provenance": prov(path),
        })
        add_edge(
            "contains", repo_ref_id, artifact_id, f"{resolved}:{path}",
            path=path, field="existence",
        )
        return artifact_id

    # Preserve explicit root documents even when the provider cannot enumerate a tree.
    root_docs: dict[str, str] = {}
    for path in ROOT_PROBE_PATHS:
        if entries and path not in by_path:
            continue
        text = read(path)
        if text is None:
            continue
        root_docs[path] = text
        add_artifact(path, _artifact_role(path), text=text)

    arch_docs = sorted(
        (
            path for path in by_path
            if PurePosixPath(path).name in ARCH_DOC_BASENAMES
        ),
        key=lambda path: (path.count("/"), path),
    )[:MAX_ARCH_DOCS]
    for path in arch_docs:
        if path in root_docs:
            continue
        add_artifact(path, _artifact_role(path))

    manifest = _parse_manifest(root_docs.get("zer0.component.yaml"))
    if manifest:
        mid = zid("implementation-manifest", f"{repo}@{resolved}")
        add_node({
            "id": mid,
            "type": "implementation_manifest",
            "label": manifest.get("name") or manifest.get("id") or repo,
            "attributes": manifest,
            "provenance": prov("zer0.component.yaml", "document"),
        })
        add_edge(
            "declares", repo_ref_id, mid, f"{resolved}:manifest",
            path="zer0.component.yaml", field="document",
        )

    package_paths = sorted(
        path for path in by_path if PurePosixPath(path).name in PACKAGE_BASENAMES
    )[:MAX_PACKAGE_MANIFESTS]
    if not package_paths:
        package_paths = [path for path in PACKAGE_BASENAMES if path in root_docs]

    packages: list[dict[str, Any]] = []
    package_by_key: dict[str, str] = {}
    for path in package_paths:
        text = read(path)
        if text is None:
            continue
        add_artifact(path, "package_metadata", text=text)
        package = _parse_package(path, text)
        if not package:
            continue
        package_id = zid("package", f"{repo}@{resolved}:{path}")
        package["repo"] = repo
        package["ref"] = ref
        package["sourcePath"] = path
        add_node({
            "id": package_id,
            "type": "package",
            "label": package["name"],
            "attributes": package,
            "provenance": prov(path, "package"),
        })
        add_edge(
            "contains_package", repo_ref_id, package_id,
            f"{resolved}:{path}:{package['name']}",
            path=path, field="package",
        )
        packages.append({"id": package_id, **package})
        package_by_key[_dep_key(package["name"])] = package_id

    # Internal package dependency edges are high-signal architecture facts and cost no
    # additional source reads once manifests are parsed.
    for package in packages:
        for dependency in package.get("dependencies") or []:
            target = package_by_key.get(_dep_key(dependency))
            if not target or target == package["id"]:
                continue
            add_edge(
                "package_depends_on", package["id"], target,
                f"{package['id']}->{target}",
                path=package["sourcePath"], field=f"dependency:{dependency}",
            )

    schema_paths = [path for path in by_path if _is_schema_path(path)][:MAX_SCHEMA_ARTIFACTS]
    for path in schema_paths:
        add_artifact(path, "schema")

    workflow_paths = [
        path for path in by_path if path.startswith(".github/workflows/") and path.lower().endswith((".yml", ".yaml"))
    ][:MAX_WORKFLOW_ARTIFACTS]
    for path in workflow_paths:
        add_artifact(path, "workflow")

    test_paths = [path for path in by_path if _is_test_path(path)]
    if test_paths:
        test_id = zid("test-surface", f"{repo}@{resolved}")
        add_node({
            "id": test_id,
            "type": "test_surface",
            "label": "tests",
            "attributes": {
                "repo": repo,
                "ref": ref,
                "fileCount": len(test_paths),
                "samples": test_paths[:MAX_TEST_SAMPLES],
            },
            "provenance": [
                prov(path, "test_file")[0] for path in test_paths[:MAX_TEST_SAMPLES]
            ],
        })
        add_edge(
            "verified_by", repo_ref_id, test_id, f"{resolved}:tests",
            path=test_paths[0], field="test_surface",
        )

    # One compressed structural node is the information bottleneck between raw tree
    # inventory and semantic zoom. It retains enough statistics to detect shape changes.
    if entries or tree_error:
        file_count = len(entries)
        total_bytes = sum(int(row["size"]) for row in entries if isinstance(row.get("size"), int))
        top_level = Counter(_top_level(str(row["path"])) for row in entries)
        extensions = Counter(_extension_key(str(row["path"])) for row in entries)
        structure_id = zid("repo-structure", f"{repo}@{resolved}")
        semantic_count = max(1, len(node_map))
        add_node({
            "id": structure_id,
            "type": "repo_structure",
            "label": "repository structure",
            "attributes": {
                "repo": repo,
                "ref": ref,
                "fileCount": file_count,
                "knownBytes": total_bytes,
                "topLevel": dict(top_level.most_common(24)),
                "extensions": dict(extensions.most_common(24)),
                "packageCount": len(packages),
                "schemaCount": len(schema_paths),
                "workflowCount": len(workflow_paths),
                "testFileCount": len(test_paths),
                "architectureDocCount": len(arch_docs),
                "treeTruncated": bool(tree.get("truncated")),
                "treeError": tree_error or tree.get("error"),
                "semanticCompressionRatio": round(file_count / semantic_count, 2) if file_count else 0,
            },
            "provenance": prov(".git", "tree"),
        })
        add_edge(
            "summarizes", repo_ref_id, structure_id, f"{resolved}:structure",
            path=".git", field="tree",
        )

    summary = _summarize_docs(root_docs)
    summary["tree"] = {
        "available": bool(entries),
        "fileCount": len(entries),
        "truncated": bool(tree.get("truncated")),
        "error": tree_error or tree.get("error"),
        "packageCount": len(packages),
        "schemaCount": len(schema_paths),
        "workflowCount": len(workflow_paths),
        "testFileCount": len(test_paths),
        "architectureDocCount": len(arch_docs),
    }

    return {
        "repo": repo,
        "ref": ref,
        "resolvedRef": resolved,
        "nodes": sorted(node_map.values(), key=lambda row: row["id"]),
        "edges": sorted(edge_map.values(), key=lambda row: row["id"]),
        "summary": summary,
    }


def _parse_manifest(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    doc = yaml.safe_load(text)
    return doc if isinstance(doc, dict) else None


def _parse_package(path: str, text: str) -> dict[str, Any] | None:
    name = PurePosixPath(path).name
    if name == "package.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        package_name = data.get("name")
        if not package_name:
            return None
        dependency_groups = {}
        dependencies: set[str] = set()
        for key in ("dependencies", "peerDependencies", "optionalDependencies", "devDependencies"):
            values = data.get(key) or {}
            if isinstance(values, dict):
                dependency_groups[key] = sorted(str(x) for x in values)
                dependencies.update(str(x) for x in values)
        return {
            "name": str(package_name),
            "version": data.get("version"),
            "ecosystem": "npm",
            "dependencies": sorted(dependencies),
            "dependencyGroups": dependency_groups,
            "workspaces": data.get("workspaces"),
        }

    if name == "pyproject.toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return None
        project = data.get("project") or {}
        poetry = ((data.get("tool") or {}).get("poetry") or {})
        package_name = project.get("name") or poetry.get("name")
        if not package_name:
            return None
        dependencies: set[str] = set()
        for raw in project.get("dependencies") or []:
            dep = _python_dependency_name(str(raw))
            if dep:
                dependencies.add(dep)
        for raw_values in (project.get("optional-dependencies") or {}).values():
            for raw in raw_values or []:
                dep = _python_dependency_name(str(raw))
                if dep:
                    dependencies.add(dep)
        poetry_deps = poetry.get("dependencies") or {}
        dependencies.update(str(key) for key in poetry_deps if str(key).lower() != "python")
        return {
            "name": str(package_name),
            "version": project.get("version") or poetry.get("version"),
            "ecosystem": "python",
            "dependencies": sorted(dependencies),
        }

    if name == "Cargo.toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return None
        package = data.get("package") or {}
        package_name = package.get("name")
        if not package_name:
            return None
        dependencies: set[str] = set()
        for key in ("dependencies", "dev-dependencies", "build-dependencies"):
            values = data.get(key) or {}
            if isinstance(values, dict):
                dependencies.update(str(x) for x in values)
        return {
            "name": str(package_name),
            "version": package.get("version"),
            "ecosystem": "cargo",
            "dependencies": sorted(dependencies),
        }

    if name == "go.mod":
        module = re.search(r"(?m)^module\s+([^\s]+)", text)
        if not module:
            return None
        dependencies = set(re.findall(r"(?m)^\s*([^\s()]+)\s+v\d", text))
        return {
            "name": module.group(1),
            "ecosystem": "go",
            "dependencies": sorted(x for x in dependencies if x != module.group(1)),
        }
    return None


def _python_dependency_name(value: str) -> str | None:
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", value)
    return match.group(1) if match else None


def _dep_key(value: str) -> str:
    return str(value).strip().lower().replace("_", "-")


def _ignored_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part in IGNORED_SEGMENTS for part in parts)


def _is_schema_path(path: str) -> bool:
    lower = path.lower()
    parts = PurePosixPath(lower).parts
    base = PurePosixPath(lower).name
    return (
        "schema" in parts
        or "schemas" in parts
        or base.endswith(".schema.json")
        or base.endswith(".proto")
        or base.endswith(".graphql")
        or base in {"openapi.json", "openapi.yaml", "openapi.yml", "swagger.json", "swagger.yaml", "swagger.yml"}
    )


def _is_test_path(path: str) -> bool:
    lower = path.lower()
    parts = PurePosixPath(lower).parts
    base = PurePosixPath(lower).name
    return (
        any(part in {"test", "tests", "__tests__", "spec", "specs"} for part in parts)
        or base.startswith("test_")
        or ".test." in base
        or ".spec." in base
    )


def _top_level(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if len(parts) > 1 else "(root)"


def _extension_key(path: str) -> str:
    base = PurePosixPath(path).name
    if base in PACKAGE_BASENAMES:
        return base
    suffix = PurePosixPath(path).suffix.lower()
    return suffix or "(none)"


def _artifact_role(path: str) -> str:
    base = PurePosixPath(path).name
    if base == "zer0.component.yaml":
        return "manifest"
    if base == "ARCHITECTURE.md":
        return "architecture"
    if base == "README.md":
        return "readme"
    if base == "AGENTS.md":
        return "agent_instructions"
    if base == "SYSTEM.md":
        return "system"
    if base == "CONTRACT.md":
        return "contract"
    if base in PACKAGE_BASENAMES:
        return "package_metadata"
    return "source"


def _summarize_docs(docs: dict[str, str]) -> dict[str, Any]:
    return {
        "hasManifest": "zer0.component.yaml" in docs,
        "hasArchitecture": "ARCHITECTURE.md" in docs,
        "hasReadme": "README.md" in docs,
        "hasAgentInstructions": "AGENTS.md" in docs,
        "packageMetadata": [
            p for p in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod") if p in docs
        ],
    }

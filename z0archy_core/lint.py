from __future__ import annotations

from collections import Counter
from typing import Any


def lint_graph(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    node_by_id = {n["id"]: n for n in nodes}
    incoming: Counter[tuple[str, str]] = Counter()
    outgoing: Counter[tuple[str, str]] = Counter()
    findings: list[dict[str, Any]] = []

    def finding(level: str, code: str, message: str, *, subject: str | None = None) -> None:
        row = {"level": level, "code": code, "message": message}
        if subject:
            row["subject"] = subject
        findings.append(row)

    for node in nodes:
        if not node.get("provenance"):
            finding("error", "provenance.node_missing", "Node has no provenance.", subject=node.get("id"))

    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source not in node_by_id:
            finding("error", "edge.source_missing", f"Unknown edge source {source!r}.", subject=edge.get("id"))
        if target not in node_by_id:
            finding("error", "edge.target_missing", f"Unknown edge target {target!r}.", subject=edge.get("id"))
        if not edge.get("provenance"):
            finding("warning", "provenance.edge_missing", "Edge has no provenance.", subject=edge.get("id"))
        if source and edge.get("type"):
            outgoing[(source, edge["type"])] += 1
        if target and edge.get("type"):
            incoming[(target, edge["type"])] += 1

    component_repo: dict[str, str] = {}
    repo_components: dict[str, set[str]] = {}
    for node in nodes:
        if node.get("type") != "component":
            continue
        attrs = node.get("attributes") or {}
        repo = attrs.get("repo")
        if not repo:
            continue
        component_repo[node["id"]] = str(repo)
        repo_components.setdefault(str(repo), set()).add(node["id"])

    declared_depends = {
        (edge.get("source"), edge.get("target"))
        for edge in edges
        if edge.get("type") == "depends_on"
    }
    declared_integrations = {
        frozenset((edge.get("source"), edge.get("target")))
        for edge in edges
        if edge.get("type") == "integrates_with"
    }

    for edge in edges:
        if edge.get("type") != "package_depends_on":
            continue
        attrs = edge.get("attributes") or {}
        if not attrs.get("derivedCrossRepo"):
            continue
        source_node = node_by_id.get(edge.get("source")) or {}
        target_node = node_by_id.get(edge.get("target")) or {}
        source_repo = (source_node.get("attributes") or {}).get("repo") or attrs.get("sourceRepo")
        target_repo = (target_node.get("attributes") or {}).get("repo") or attrs.get("targetRepo")
        source_components = repo_components.get(str(source_repo), set())
        target_components = repo_components.get(str(target_repo), set())
        if not source_components or not target_components:
            finding(
                "info",
                "drift.package_dependency_unmapped",
                f"Cross-repo package dependency {source_repo} -> {target_repo} cannot be mapped to registered components.",
                subject=edge.get("id"),
            )
            continue
        declared = any(
            (source_component, target_component) in declared_depends
            or frozenset((source_component, target_component)) in declared_integrations
            for source_component in source_components
            for target_component in target_components
        )
        if not declared:
            finding(
                "warning",
                "drift.cross_repo_package_dependency_undeclared",
                f"Implementation package dependency {source_repo} -> {target_repo} has no matching z0 depends_on/integrates_with declaration.",
                subject=edge.get("id"),
            )

    for node in nodes:
        ntype = node.get("type")
        attrs = node.get("attributes") or {}
        nid = node.get("id")

        if ntype == "evidence_dependency":
            unresolved = attrs.get("unresolvedEndpoints") or []
            if unresolved:
                finding(
                    "error",
                    "evidence.unresolved_endpoint",
                    "EvidenceDependency has unresolved endpoint(s): " + ", ".join(map(str, unresolved)),
                    subject=nid,
                )
            if not attrs.get("required_evidence"):
                finding("error", "evidence.required_missing", "EvidenceDependency has no required evidence.", subject=nid)
            if not attrs.get("invariants"):
                finding("error", "evidence.invariants_missing", "EvidenceDependency has no invariants.", subject=nid)
            if not attrs.get("invalidators"):
                finding("warning", "evidence.invalidators_missing", "EvidenceDependency has no invalidators.", subject=nid)
            retrieval = attrs.get("retrieval") or {}
            if not retrieval.get("fastest"):
                finding("warning", "evidence.retrieval_missing", "EvidenceDependency has no fastest retrieval path.", subject=nid)
            if not attrs.get("confidence"):
                finding("warning", "evidence.confidence_missing", "EvidenceDependency has no confidence class.", subject=nid)

        elif ntype == "representation":
            if not attrs.get("scale"):
                finding("warning", "representation.scale_missing", "Representation has no scale.", subject=nid)
            if not attrs.get("sensitivity"):
                finding("warning", "representation.sensitivity_missing", "Representation has no sensitivity.", subject=nid)
            if not attrs.get("evidence"):
                finding("warning", "representation.evidence_missing", "Representation has no declared evidence.", subject=nid)

        elif ntype == "interface":
            if incoming[(nid, "provides")] == 0:
                finding("warning", "interface.provider_missing", "Interface has no declared provider.", subject=nid)

        elif ntype == "mechanism":
            implemented = (
                incoming[(nid, "implemented_by")]
                + outgoing[(nid, "implemented_by")]
                + outgoing[(nid, "implemented_in_repo")]
            )
            if implemented == 0:
                finding("warning", "mechanism.implementation_missing", "Mechanism has no declared implementation.", subject=nid)

    findings.sort(key=lambda row: ({"error": 0, "warning": 1, "info": 2}.get(row["level"], 9), row["code"], row.get("subject", "")))
    return findings


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["level"] for row in findings)
    return {level: counts.get(level, 0) for level in ("error", "warning", "info")}

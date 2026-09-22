from __future__ import annotations

import re
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def lint_graph(graph: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    node_ids = [str(n.get("id")) for n in nodes]
    edge_ids = [str(e.get("id")) for e in edges]
    node_set = set(node_ids)

    _duplicates(node_ids, "node", findings)
    _duplicates(edge_ids, "edge", findings)

    for node in nodes:
        nid = str(node.get("id"))
        if not node.get("provenance"):
            _finding(findings, "missing-node-provenance", "error", nid, "Node has no provenance.")
        if node.get("type") == "interface":
            owner = (node.get("attributes") or {}).get("owner")
            if owner and not any(
                n.get("type") == "component"
                and (n.get("attributes") or {}).get("component_id") == owner
                for n in nodes
            ):
                _finding(
                    findings,
                    "unknown-interface-owner",
                    "error",
                    nid,
                    f"Interface owner {owner!r} is not a declared component.",
                )
        if node.get("type") == "harness" and (node.get("attributes") or {}).get("catalog_gap"):
            _finding(
                findings,
                "harness-catalog-gap",
                "warning",
                nid,
                "Harness is used by Zer0 but lacks an AODL catalog id.",
            )
        _check_moving_declared_refs(node.get("provenance") or [], nid, findings)

    for edge in edges:
        eid = str(edge.get("id"))
        if edge.get("source") not in node_set:
            _finding(findings, "dangling-edge-source", "error", eid, f"Missing source {edge.get('source')}.")
        if edge.get("target") not in node_set:
            _finding(findings, "dangling-edge-target", "error", eid, f"Missing target {edge.get('target')}.")
        provenance = edge.get("provenance") or []
        if not provenance:
            _finding(findings, "missing-edge-provenance", "error", eid, "Relation has no provenance.")
        dep = edge.get("evidenceDependency") or {}
        if not dep:
            _finding(findings, "missing-evidence-dependency", "error", eid, "Relation has no EvidenceDependency.")
        else:
            for field in ("requiredEvidence", "invariants", "invalidators", "abstainWhen"):
                if not dep.get(field):
                    _finding(
                        findings,
                        "incomplete-evidence-dependency",
                        "error",
                        eid,
                        f"EvidenceDependency field {field!r} is empty.",
                    )
            confidence = dep.get("confidence") or {}
            if confidence.get("numericScore") is not None:
                _finding(
                    findings,
                    "fabricated-confidence",
                    "error",
                    eid,
                    "Numeric confidence is unsupported without a measured calibration source.",
                )
            if not dep.get("retrieval"):
                _finding(
                    findings,
                    "missing-retrieval-recipe",
                    "warning",
                    eid,
                    "Relation cannot currently reconstruct its evidence from a retrieval recipe.",
                )
        _check_moving_declared_refs(provenance, eid, findings)

    return sorted(findings, key=lambda f: (_severity_rank(f["severity"]), f["code"], f["subject"]))


def highest_severity(findings: list[dict[str, Any]]) -> str | None:
    if any(f["severity"] == "error" for f in findings):
        return "error"
    if any(f["severity"] == "warning" for f in findings):
        return "warning"
    return None


def _check_moving_declared_refs(
    provenance: list[dict[str, Any]],
    subject: str,
    findings: list[dict[str, Any]],
) -> None:
    for p in provenance:
        if p.get("class") != "declared":
            continue
        ref = str(p.get("ref") or "")
        if ref and not _SHA_RE.fullmatch(ref):
            _finding(
                findings,
                "moving-declared-ref",
                "warning",
                subject,
                f"Declared evidence uses moving ref {ref!r}; prefer an immutable commit SHA.",
            )


def _duplicates(values: list[str], kind: str, findings: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            _finding(findings, f"duplicate-{kind}-id", "error", value, f"Duplicate {kind} id.")
        seen.add(value)


def _finding(
    findings: list[dict[str, Any]],
    code: str,
    severity: str,
    subject: str,
    detail: str,
) -> None:
    findings.append({
        "code": code,
        "severity": severity,
        "subject": subject,
        "detail": detail,
    })


def _severity_rank(value: str) -> int:
    return {"error": 0, "warning": 1, "info": 2}.get(value, 9)

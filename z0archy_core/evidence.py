from __future__ import annotations

from typing import Any


def build_evidence_dependency(
    provenance: list[dict[str, Any]],
    *,
    source_id: str,
    target_id: str,
    verified_at: str | None,
) -> dict[str, Any]:
    """Build an epistemic contract for one semantic relation.

    Confidence is categorical and authority-based rather than an invented numeric score.
    The dependency describes what evidence is required to assert the relation, what must
    remain true, what invalidates it, and when consumers should abstain.
    """
    classes = {str(p.get("class", "unknown")) for p in provenance}
    authority = _authority_level(classes)
    required = [
        {
            "class": p.get("class"),
            "source": p.get("source"),
            "ref": p.get("ref"),
            "path": p.get("path"),
            "field": p.get("field"),
        }
        for p in provenance
    ]
    retrieval = [
        {
            "kind": "git",
            "source": p.get("source"),
            "ref": p.get("ref"),
            "path": p.get("path"),
            "field": p.get("field"),
        }
        for p in provenance
        if p.get("source") and p.get("ref") and p.get("path")
    ]

    invariants = [
        f"semantic endpoint exists: {source_id}",
        f"semantic endpoint exists: {target_id}",
        "every required evidence locator resolves to the asserted source/ref/path",
    ]
    invalidators = [
        "required evidence content or declared field changes",
        "either semantic endpoint is removed, superseded, or changes identity",
    ]
    abstain = [
        "required evidence cannot be resolved",
        "evidence source and asserted ref disagree",
    ]

    if "implemented" in classes:
        invariants.append("implementation evidence remains tied to the exact inspected ref")
        invalidators.append("the selected implementation ref changes")
    if "observed" in classes:
        invariants.append("observation coverage and timestamp remain applicable to the claim")
        invalidators.append("newer observation contradicts or supersedes this relation")
        abstain.append("observation coverage is insufficient for the requested conclusion")
    if "declared" in classes:
        invalidators.append("canonical architecture declaration changes")

    return {
        "requiredEvidence": required,
        "invariants": invariants,
        "invalidators": invalidators,
        "abstainWhen": abstain,
        "retrieval": retrieval,
        "confidence": {
            "basis": "authority",
            "level": authority,
            "numericScore": None,
        },
        "lastVerified": verified_at,
    }


def attach_evidence_dependencies(
    edges: list[dict[str, Any]],
    *,
    verified_at: str | None,
) -> list[dict[str, Any]]:
    for edge in edges:
        if edge.get("evidenceDependency"):
            continue
        edge["evidenceDependency"] = build_evidence_dependency(
            list(edge.get("provenance") or []),
            source_id=str(edge.get("source", "")),
            target_id=str(edge.get("target", "")),
            verified_at=verified_at,
        )
    return edges


def _authority_level(classes: set[str]) -> str:
    if "declared" in classes:
        return "canonical-declaration"
    if "implemented" in classes:
        return "exact-implementation"
    if "observed" in classes:
        return "observation"
    if "historical" in classes:
        return "historical"
    if "derived" in classes:
        return "derived"
    return "unknown"

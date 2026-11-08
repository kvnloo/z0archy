from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from .graph import zid


SUPPORTED_VERSION = 1
RELATION_KINDS = {"calls", "references", "implements", "inherits", "imports", "verified_by"}


def normalize_code_intelligence_snapshot(
    snapshot: dict[str, Any],
    *,
    repo: str,
    resolved_ref: str,
) -> dict[str, Any]:
    """Normalize provider-specific code intelligence into exact-ref graph evidence.

    This module deliberately does not parse source code or choose an index provider.
    Adapters (SCIP, Glean, open-codebase-index, ctags, etc.) may emit the small
    snapshot contract consumed here. Provider output remains implemented evidence
    tied to one exact source revision; it never becomes canonical architecture truth.
    """
    if snapshot.get("version") != SUPPORTED_VERSION:
        raise ValueError(f"unsupported code-intelligence version: {snapshot.get('version')!r}")

    provider = _required_text(snapshot, "provider")
    source_revision = _required_text(snapshot, "sourceRevision")
    input_fingerprint = _required_text(snapshot, "inputFingerprint")
    confidence = _required_text(snapshot, "confidence")

    result: dict[str, Any] = {
        "version": SUPPORTED_VERSION,
        "provider": provider,
        "repo": repo,
        "resolvedRef": resolved_ref,
        "sourceRevision": source_revision,
        "inputFingerprint": input_fingerprint,
        "confidence": confidence,
        "status": "current",
        "nodes": [],
        "edges": [],
        "diagnostics": [],
    }

    declared_repo = snapshot.get("repo")
    if declared_repo is not None and str(declared_repo) != repo:
        result["status"] = "stale"
        result["diagnostics"] = [{
            "code": "repository_mismatch",
            "expected": repo,
            "actual": str(declared_repo),
        }]
        return result

    if source_revision != resolved_ref:
        result["status"] = "stale"
        result["diagnostics"] = [{
            "code": "source_revision_mismatch",
            "expected": resolved_ref,
            "actual": source_revision,
        }]
        return result

    records: list[tuple[dict[str, Any], bool]] = []
    records.extend((row, False) for row in _dict_rows(snapshot.get("symbols")))
    records.extend((row, True) for row in _dict_rows(snapshot.get("testSymbols")))

    grouped: dict[str, list[tuple[dict[str, Any], bool]]] = defaultdict(list)
    for row, is_test in records:
        external_id = _text(row.get("id"))
        if not external_id:
            result["diagnostics"].append({
                "code": "invalid_symbol",
                "reason": "missing id",
                "path": _text(row.get("path")),
            })
            continue
        grouped[external_id].append((row, is_test))

    symbol_ids: dict[str, str] = {}
    for external_id in sorted(grouped):
        candidates = grouped[external_id]
        fingerprints = {
            _canonical_symbol_record(row, is_test)
            for row, is_test in candidates
        }
        if len(fingerprints) != 1:
            result["diagnostics"].append({
                "code": "ambiguous_symbol",
                "externalId": external_id,
                "candidates": len(fingerprints),
            })
            continue

        row, is_test = sorted(
            candidates,
            key=lambda pair: _canonical_symbol_record(pair[0], pair[1]),
        )[0]
        node = _symbol_node(
            row,
            is_test=is_test,
            repo=repo,
            resolved_ref=resolved_ref,
            provider=provider,
            input_fingerprint=input_fingerprint,
            confidence=confidence,
        )
        if node is None:
            result["diagnostics"].append({
                "code": "invalid_symbol",
                "reason": "missing name or path",
                "externalId": external_id,
            })
            continue
        symbol_ids[external_id] = node["id"]
        result["nodes"].append(node)

    for relation in sorted(
        _dict_rows(snapshot.get("relations")),
        key=_canonical_json,
    ):
        kind = _text(relation.get("kind"))
        source_external = _text(relation.get("source"))
        target_external = _text(relation.get("target"))
        if kind not in RELATION_KINDS:
            result["diagnostics"].append({
                "code": "unsupported_relation_kind",
                "kind": kind,
                "source": source_external,
                "target": target_external,
            })
            continue
        source_id = symbol_ids.get(source_external or "")
        target_id = symbol_ids.get(target_external or "")
        if not kind or not source_id or not target_id:
            result["diagnostics"].append({
                "code": "unresolved_relation",
                "kind": kind,
                "source": source_external,
                "target": target_external,
            })
            continue

        relation_path = _text(relation.get("path"))
        line = _positive_int(relation.get("line"))
        edge_id = zid(
            "edge",
            (
                f"code-{kind}:{repo}@{resolved_ref}:{provider}:"
                f"{source_external}->{target_external}:"
                f"{relation_path or ''}:{line or ''}"
            ),
        )
        provenance = _provenance(
            repo=repo,
            resolved_ref=resolved_ref,
            provider=provider,
            input_fingerprint=input_fingerprint,
            confidence=confidence,
            path=relation_path,
            field=f"code_intelligence.relation.{kind}",
        )
        result["edges"].append({
            "id": edge_id,
            "type": f"code_{kind}",
            "source": source_id,
            "target": target_id,
            "attributes": {
                "provider": provider,
                "sourceRevision": resolved_ref,
                "inputFingerprint": input_fingerprint,
                "confidence": confidence,
                "path": relation_path,
                "line": line,
            },
            "provenance": provenance,
        })

    result["nodes"].sort(key=lambda row: row["id"])
    result["edges"].sort(key=lambda row: row["id"])
    result["diagnostics"].sort(key=_canonical_json)
    return result


def _symbol_node(
    row: dict[str, Any],
    *,
    is_test: bool,
    repo: str,
    resolved_ref: str,
    provider: str,
    input_fingerprint: str,
    confidence: str,
) -> dict[str, Any] | None:
    external_id = _text(row.get("id"))
    name = _text(row.get("name"))
    path = _text(row.get("path"))
    if not external_id or not name or not path:
        return None

    node_id = zid(
        "code-symbol",
        f"{repo}@{resolved_ref}:{provider}:{external_id}",
    )
    attributes = {
        "repo": repo,
        "resolvedRef": resolved_ref,
        "provider": provider,
        "sourceRevision": resolved_ref,
        "inputFingerprint": input_fingerprint,
        "confidence": confidence,
        "externalId": external_id,
        "kind": _text(row.get("kind")) or ("test" if is_test else "symbol"),
        "path": path,
        "line": _positive_int(row.get("line")),
        "endLine": _positive_int(row.get("endLine")),
        "signature": _text(row.get("signature")),
        "isTest": is_test,
    }
    return {
        "id": node_id,
        "type": "code_symbol",
        "label": name,
        "attributes": attributes,
        "provenance": _provenance(
            repo=repo,
            resolved_ref=resolved_ref,
            provider=provider,
            input_fingerprint=input_fingerprint,
            confidence=confidence,
            path=path,
            field="code_intelligence.symbol",
        ),
    }


def _provenance(
    *,
    repo: str,
    resolved_ref: str,
    provider: str,
    input_fingerprint: str,
    confidence: str,
    path: str | None,
    field: str,
) -> list[dict[str, Any]]:
    return [{
        "class": "implemented",
        "source": repo,
        "ref": resolved_ref,
        "path": path or ".git",
        "field": field,
        "provider": provider,
        "inputFingerprint": input_fingerprint,
        "confidence": confidence,
    }]


def _required_text(snapshot: dict[str, Any], field: str) -> str:
    value = _text(snapshot.get(field))
    if not value:
        raise ValueError(f"code-intelligence snapshot requires {field}")
    return value


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _canonical_symbol_record(row: dict[str, Any], is_test: bool) -> str:
    return _canonical_json({
        "id": _text(row.get("id")),
        "name": _text(row.get("name")),
        "kind": _text(row.get("kind")),
        "path": _text(row.get("path")),
        "line": _positive_int(row.get("line")),
        "endLine": _positive_int(row.get("endLine")),
        "signature": _text(row.get("signature")),
        "isTest": is_test,
    })


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

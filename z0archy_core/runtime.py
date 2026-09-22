from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOKENOMICS_REPORT_SCHEMA = "tokenomics.report.v1"
Z0ARCHY_TOKENOMICS_SCHEMA = "z0archy.runtime.tokenomics.v1"


def normalize_tokenomics_report(
    report: dict[str, Any],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Normalize Tokenomics-owned report semantics without recomputing economics.

    z0archy is only a projection surface. It preserves Tokenomics' measured,
    estimated and unknown tiers separately and intentionally redacts underlying
    local source paths.
    """
    if report.get("schema") != TOKENOMICS_REPORT_SCHEMA:
        raise ValueError(
            f"expected {TOKENOMICS_REPORT_SCHEMA!r}, got {report.get('schema')!r}"
        )

    totals = dict(report.get("totals") or {})
    savings = dict(report.get("savings") or {})
    tiers = dict(savings.get("tiers") or {})
    verified = dict(report.get("verified_outcomes") or {})
    prepare = dict(report.get("prepare_funnel") or {})
    economics = dict(report.get("economics") or {})
    quality = dict(report.get("data_quality") or {})

    # Do not accept a projection that has collapsed the tier distinction.
    measured = dict(tiers.get("measured") or {})
    estimated = dict(tiers.get("estimated") or {})
    unknown = dict(tiers.get("unknown") or {})
    if "measured_tokens_avoided" in totals and "tokens_avoided" not in measured:
        measured["tokens_avoided"] = totals.get("measured_tokens_avoided")
    if "estimated_tokens_avoided" in totals and "tokens_avoided" not in estimated:
        estimated["tokens_avoided"] = totals.get("estimated_tokens_avoided")

    source_rows = report.get("sources") or []
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema": Z0ARCHY_TOKENOMICS_SCHEMA,
        "truthClass": "observed",
        "owner": "kvnloo/tokenomics",
        "sourceSchema": TOKENOMICS_REPORT_SCHEMA,
        "generatedAt": generated_at,
        "range": report.get("range"),
        "period": report.get("period") or {},
        "nEvents": report.get("n_events"),
        "totals": {
            "baseline_tokens": totals.get("baseline_tokens"),
            "actual_frontier_tokens": totals.get("actual_frontier_tokens"),
            "measured_tokens_avoided": measured.get("tokens_avoided"),
            "estimated_tokens_avoided": estimated.get("tokens_avoided"),
            "unknown_or_no_baseline_tokens": totals.get("unknown_or_no_baseline_tokens"),
            "reduction_vs_baseline": totals.get("reduction_vs_baseline"),
        },
        "savings": {
            "measured": measured,
            "estimated": estimated,
            "unknown": unknown,
            "rule": savings.get("rule") or "Never collapse measured and estimated savings.",
        },
        "verifiedOutcomes": {
            "verified_tasks": verified.get("verified_tasks"),
            "tokens_per_verified_task": verified.get("tokens_per_verified_task"),
            "baseline_tokens_per_verified_task": verified.get("baseline_tokens_per_verified_task"),
            "reduction_per_verified": verified.get("reduction_per_verified"),
        },
        "byMechanism": list(report.get("by_mechanism") or []),
        "byHarness": list(report.get("by_harness") or []),
        "prepareFunnel": {
            key: prepare.get(key)
            for key in (
                "prepared",
                "consumed",
                "expired",
                "invalidated",
                "would_prepare",
                "prepare_hit_rate",
                "latency_hidden_ms",
                "speculation_overhead_ms",
                "net_prepare_value_ms",
                "prepare_efficiency",
                "counterfactual_blocking_ms",
                "frontier_tokens_replaced_on_consume",
            )
            if key in prepare
        },
        "economics": {
            "observed_cost_usd": economics.get("observed_cost_usd"),
            "baseline_cost_usd": economics.get("baseline_cost_usd"),
            "note": economics.get("note"),
        },
        "dataQuality": quality,
        "provenance": {
            "sourceCount": len(source_rows),
            "sourcePathsRedacted": True,
            "inputPathProvided": source_path is not None,
        },
    }

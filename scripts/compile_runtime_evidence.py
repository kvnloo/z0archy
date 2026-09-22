#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.runtime_evidence import compile_runtime_evidence


def main() -> None:
    p = argparse.ArgumentParser(
        description="Compile privacy-bounded local runtime evidence for z0archy"
    )
    p.add_argument("--tokenomics-events", action="append", default=[])
    p.add_argument("--agenttrace-report", action="append", default=[])
    p.add_argument("--aodl-document", action="append", default=[])
    p.add_argument("--max-tokenomics-events", type=int, default=300)
    p.add_argument("--max-agenttrace-sessions", type=int, default=100)
    p.add_argument("--output", default="generated/runtime-evidence.json")
    args = p.parse_args()

    tokenomics = list(args.tokenomics_events)
    if not tokenomics:
        candidate = Path("~/.local/share/tokenomics/events.jsonl").expanduser()
        if candidate.is_file():
            tokenomics.append(str(candidate))

    graph = compile_runtime_evidence(
        tokenomics_paths=tokenomics,
        agenttrace_paths=args.agenttrace_report,
        aodl_paths=args.aodl_document,
        max_tokenomics_events=args.max_tokenomics_events,
        max_agenttrace_sessions=args.max_agenttrace_sessions,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    summary = graph["summary"]
    print(
        f"runtime evidence: {summary['traceCount']} traces, "
        f"{summary['tokenomicsEventCount']} tokenomics events, "
        f"{summary['agenttraceSessionCount']} sessions, "
        f"{summary['aodlWorldCount']} AODL worlds"
    )


if __name__ == "__main__":
    main()

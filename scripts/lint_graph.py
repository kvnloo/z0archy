#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.lint import lint_graph, summarize_findings


def main() -> None:
    p = argparse.ArgumentParser(description="Lint z0archy semantic and epistemic graph invariants")
    p.add_argument("graph", nargs="?", default="generated/graph.json")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.add_argument("--fail-on", choices=["none", "warning", "error"], default="error")
    args = p.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    findings = lint_graph(graph)
    summary = summarize_findings(findings)

    if args.json:
        print(json.dumps({"summary": summary, "findings": findings}, indent=2))
    else:
        for row in findings:
            subject = f" [{row['subject']}]" if row.get("subject") else ""
            print(f"{row['level'].upper():7} {row['code']}{subject}: {row['message']}")
        print(f"lint: {summary['error']} error(s), {summary['warning']} warning(s), {summary['info']} info")

    fail = (
        args.fail_on == "error" and summary["error"] > 0
        or args.fail_on == "warning" and (summary["error"] > 0 or summary["warning"] > 0)
    )
    raise SystemExit(1 if fail else 0)


if __name__ == "__main__":
    main()

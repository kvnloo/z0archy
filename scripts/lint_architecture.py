#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.lint import lint_graph


def main() -> None:
    p = argparse.ArgumentParser(description="Lint a z0archy semantic graph")
    p.add_argument("graph", nargs="?", default="generated/graph.json")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    args = p.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    findings = lint_graph(graph)

    if args.format == "json":
        print(json.dumps({"findings": findings}, indent=2))
    else:
        if not findings:
            print("ok: no architecture lint findings")
        for finding in findings:
            print(
                f"{finding['severity'].upper():7} {finding['code']}: "
                f"{finding['subject']} — {finding['detail']}"
            )

    should_fail = (
        args.fail_on == "warning" and any(f["severity"] in {"warning", "error"} for f in findings)
    ) or (
        args.fail_on == "error" and any(f["severity"] == "error" for f in findings)
    )
    raise SystemExit(1 if should_fail else 0)


if __name__ == "__main__":
    main()

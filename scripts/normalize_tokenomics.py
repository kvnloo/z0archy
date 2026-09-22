#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.runtime import normalize_tokenomics_report


def main() -> None:
    p = argparse.ArgumentParser(description="Project tokenomics.report.v1 into a privacy-safe z0archy runtime overlay")
    p.add_argument("report", help="Tokenomics report JSON")
    p.add_argument("--output", default="generated/runtime/tokenomics.json")
    args = p.parse_args()

    source = Path(args.report).expanduser()
    report = json.loads(source.read_text(encoding="utf-8"))
    overlay = normalize_tokenomics_report(report, source_path=source)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(overlay, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(overlay['byMechanism'])} mechanism row(s), {len(overlay['byHarness'])} harness row(s)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.virtual import diff_graphs


def main() -> None:
    p = argparse.ArgumentParser(description="Diff two z0archy semantic graph snapshots")
    p.add_argument("base")
    p.add_argument("head")
    p.add_argument("--output")
    args = p.parse_args()

    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    head = json.loads(Path(args.head).read_text(encoding="utf-8"))
    diff = diff_graphs(base, head)
    text = json.dumps(diff, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()

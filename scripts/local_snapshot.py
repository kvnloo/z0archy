#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from z0archy_core.local_git import build_local_snapshot


def main() -> None:
    p = argparse.ArgumentParser(description="Observe local Git clones and worktrees without mutating them")
    p.add_argument("--workspace", action="append", required=True, help="root to scan; repeatable")
    p.add_argument("--output", default="generated/local-state.json")
    args = p.parse_args()
    data = build_local_snapshot(args.workspace)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(data['repositories'])} repositories")


if __name__ == "__main__":
    main()

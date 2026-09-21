#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from z0archy_core.github import GitHubGraphQLClient, fetch_branch_index


def main() -> None:
    p = argparse.ArgumentParser(description="Build cached GitHub branch index for z0archy")
    p.add_argument("--graph", default="generated/graph.json")
    p.add_argument("--output", default="generated/github-index.json")
    p.add_argument("--cache", default=".cache/github.sqlite3")
    p.add_argument("--cache-ttl", type=int, default=10800, help="seconds; default 3h")
    args = p.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    repos = sorted({n["attributes"]["repo"] for n in graph["nodes"] if n.get("type") == "repository"})
    client = GitHubGraphQLClient(cache_path=args.cache, ttl_seconds=args.cache_ttl)
    try:
        repositories = fetch_branch_index(repos, client)
        rl = client.last_rate_limit
    finally:
        client.close()
    payload = {
        "schemaVersion": "0.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "truthClass": "observed",
        "source": "github",
        "rateLimit": {"cost": rl.cost, "remaining": rl.remaining, "resetAt": rl.reset_at},
        "repositories": repositories,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(repositories)} repositories")


if __name__ == "__main__":
    main()

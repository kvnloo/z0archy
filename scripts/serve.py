#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import json
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from z0archy_core.local_git import build_local_snapshot_from_git_roots, discover_git_roots


def write_snapshot(git_roots: list[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(build_local_snapshot_from_git_roots(git_roots), indent=2) + "\n", encoding="utf-8")
    tmp.replace(output)


def main() -> None:
    p = argparse.ArgumentParser(description="Serve z0archy with a live read-only local Git overlay")
    p.add_argument("--workspace", action="append", required=True, help="workspace root to scan; repeatable")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--rediscover-interval", type=float, default=30.0)
    p.add_argument("--output", default="generated/local-state.json")
    args = p.parse_args()
    output = Path(args.output)
    git_roots = discover_git_roots(args.workspace)
    write_snapshot(git_roots, output)

    stop = threading.Event()
    def watch() -> None:
        roots = list(git_roots)
        last_discovery = 0.0
        while not stop.wait(args.interval):
            try:
                now = time.monotonic()
                if now - last_discovery >= args.rediscover_interval:
                    roots = discover_git_roots(args.workspace)
                    last_discovery = now
                write_snapshot(roots, output)
            except Exception as exc:
                print(f"local scan failed: {exc}")

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    server = ThreadingHTTPServer((args.host, args.port), SimpleHTTPRequestHandler)
    print(f"z0archy: http://{args.host}:{args.port} (watching {len(git_roots)} repos under {', '.join(args.workspace)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()

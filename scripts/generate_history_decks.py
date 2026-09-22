#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _load_deck_module():
    script = Path(__file__).resolve().parent / "generate_deck.py"
    spec = importlib.util.spec_from_file_location("z0archy_generate_deck", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    p = argparse.ArgumentParser(description="Precompile graphcon-deck views for ActiveGraph history snapshots")
    p.add_argument("--index", default="generated/history-index.json")
    p.add_argument("--history-dir", default="generated/history")
    p.add_argument("--output-dir", default="generated/history-decks")
    args = p.parse_args()

    index_path = Path(args.index)
    if not index_path.is_file():
        print("history index absent; nothing to compile")
        return

    index = json.loads(index_path.read_text(encoding="utf-8"))
    history_dir = Path(args.history_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    deck_module = _load_deck_module()

    compiled = 0
    for entry in index.get("entries") or []:
        digest = entry.get("hash")
        if not digest:
            continue
        graph_path = history_dir / f"{digest}.json"
        if not graph_path.is_file():
            continue
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        deck = deck_module.build(graph)
        deck.setdefault("meta", {})["event"] = "architecture history"
        deck["meta"]["date"] = entry.get("createdAt") or digest[:12]
        deck["meta"]["historyHash"] = digest
        target = output_dir / f"{digest}.json"
        target.write_text(json.dumps(deck, indent=2) + "\n", encoding="utf-8")
        entry["deckPath"] = f"generated/history-decks/{digest}.json"
        compiled += 1

    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"compiled {compiled} historical deck(s)")


if __name__ == "__main__":
    main()

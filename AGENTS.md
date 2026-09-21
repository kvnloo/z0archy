# AGENTS.md

## Purpose

z0archy is the visual architecture projection for Zer0.

## Invariants

1. `kvnloo/z0` is the canonical owner of component boundaries, profiles and cross-system interfaces.
2. `deck.json` is generated evidence. Do not hand-maintain architecture truth here.
3. z0archy owns presentation only: spatial layout, navigation, graph interaction and publication.
4. Runtime and Git state may be projected here only as non-canonical observed evidence; their originating systems remain authoritative.
5. Component implementation details stay in component repositories.
6. Preserve the upstream graph-deck MIT notice when changing the browser engine.

## Normal change flow

- architecture fact changed: update `kvnloo/z0`, then regenerate this deck
- visual behavior changed: edit `index.html` here
- canonical graph projection changed: edit `z0archy_core/graph.py` / `scripts/generate_graph.py` and add validation
- visual projection changed: edit `scripts/generate_deck.py` or browser presentation code
- source observation changed: edit `z0archy_core/github.py` or `z0archy_core/local_git.py` and add deterministic fixtures
- never make a z0archy-only architecture fact that conflicts with the z0 registry

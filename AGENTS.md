# AGENTS.md

## Purpose

z0archy is the visual architecture projection for Zer0.

## Invariants

1. `kvnloo/z0` is the canonical owner of component boundaries, profiles and cross-system interfaces.
2. `deck.json` is generated evidence. Do not hand-maintain architecture truth here.
3. z0archy owns presentation only: spatial layout, navigation, graph interaction and publication.
4. Runtime state belongs in operational surfaces, not this static architecture map.
5. Component implementation details stay in component repositories.
6. Preserve the upstream graph-deck MIT notice when changing the browser engine.

## Normal change flow

- architecture fact changed: update `kvnloo/z0`, then regenerate this deck
- visual behavior changed: edit `index.html` here
- projection logic changed: edit `scripts/generate_deck.py` and add/adjust validation
- never make a z0archy-only architecture fact that conflicts with the z0 registry

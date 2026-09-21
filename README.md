# z0archy

A dynamic, zoomable architecture map of the Zer0 ecosystem.

**Canonical architecture truth lives in [`kvnloo/z0`](https://github.com/kvnloo/z0).** This repository is a visual projection of that registry, not a second architecture registry.

The interaction engine is adapted from Yohei Nakajima's MIT-licensed `graphcon-deck`: authored spatial nodes, scene navigation, pan/zoom, mobile pinch/zoom, cross-scene edges, and a whole-graph view.

## What this repo owns

- the visual/spatial presentation of Zer0 architecture
- graph-deck interaction behavior
- generated `deck.json` consumed by the static site
- GitHub Pages publication and sync automation

## What it does not own

- component boundaries or dependency truth
- implementation docs
- runtime state
- routing policy, measurements, experiments, or research evidence

Those stay in their owning repositories and in the canonical `kvnloo/z0` registry.

## Local preview

```bash
python -m http.server 8000
# open http://localhost:8000
```

Regenerate the deck from the current public z0 registry:

```bash
python -m pip install -r requirements.txt
python scripts/generate_deck.py
```

## Upstream

Visual engine: https://github.com/kvnloo/graphcon-deck  
Original author: Yohei Nakajima

See `NOTICE.md` and `LICENSE`.

# z0archy

A dynamic, zoomable architecture explorer for the Zer0 ecosystem.

**Canonical architecture truth lives in [`kvnloo/z0`](https://github.com/kvnloo/z0).**
z0archy is a projection and observation surface, not a second architecture registry.

The presentation engine is adapted from Yohei Nakajima's MIT-licensed
[`graphcon-deck`](https://github.com/kvnloo/graphcon-deck). The temporal model is
designed to map cleanly onto the event-sourced
[`ActiveGraph`](https://github.com/kvnloo/activegraph) substrate as historical
snapshots and runtime observations are added.

## Data model

The pipeline is now:

```text
kvnloo/z0 registry
      ↓ declared facts
generated/graph.json
      ↓ projection
deck.json → graphcon-deck UI

GitHub refs ───────┐
local worktrees ───┴→ observed evidence overlays
```

`generated/graph.json` carries stable `z0://...` IDs and provenance for components,
repositories, interfaces, profiles, and their relationships. The deck is presentation
state derived from that IR.

Declared z0 facts never get silently overwritten by Git or local observations.

## Hosted mode

GitHub Pages rebuilds every three hours and on `main` pushes.

The build:

1. compiles the current public `kvnloo/z0` registry into graph IR;
2. batches referenced repositories into GitHub GraphQL branch queries;
3. persists GraphQL responses in an Actions-restored SQLite cache;
4. regenerates the graphcon-deck projection; and
5. publishes a static site whose visitors make no GitHub API calls.

The source selector can inspect every indexed branch for each registered component.

## Local mode

Local mode is read-only toward source repositories.

```bash
python -m pip install -r requirements.txt
python scripts/generate_graph.py
python scripts/generate_deck.py
python scripts/serve.py --workspace ~/src/zer0
```

Open <http://127.0.0.1:8000>.

The watcher discovers Git repositories and `git worktree` checkouts, normalizes GitHub
remotes so multiple worktrees remain one repository identity, and exposes each checkout's
branch, HEAD, dirty count, and ahead/behind state.

Known repositories are refreshed every two seconds. Expensive workspace rediscovery is
only repeated periodically, so large worktree fleets do not require a full filesystem walk
on every UI refresh.

Use more than one workspace root when needed:

```bash
python scripts/serve.py \
  --workspace ~/src/zer0 \
  --workspace ~/src/experiments
```

## GitHub API budget

The GitHub source layer was informed by the GraphQL pagination and SQLite ingestion
patterns in `kvnloo/gh-contrib-archive`, but z0archy adds API-specific caching and
budget controls:

- query + variables are hashed into deterministic SQLite cache keys;
- repository branch queries are batched, up to 20 repos per GraphQL request;
- only repositories with more than 100 branches require follow-up pagination;
- stale cached responses can be used during transient API failures;
- `rateLimit { cost remaining resetAt }` is captured on every live query; and
- Pages restores `.cache/github.sqlite3` between scheduled builds.

## Validation

```bash
python -m unittest discover -s tests -v
python scripts/validate_graph.py generated/graph.json
python scripts/validate_deck.py deck.json
```

Tests include a real temporary Git repository with a second Git worktree to enforce the
repository-vs-checkout identity boundary.

## Ownership

z0archy owns presentation, graph projection logic, source observations, provenance, and
publication.

It does **not** own component boundaries, routing policy, measurements, research evidence,
or implementation details. Runtime and Git state may be displayed as observed evidence,
but remain owned by their originating systems.

See `docs/ARCHITECTURE.md`, `AGENTS.md`, `NOTICE.md`, and `LICENSE`.

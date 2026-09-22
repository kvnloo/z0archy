# z0archy

A dynamic, zoomable architecture explorer and semantic world model for the Zer0 ecosystem.

**Canonical architecture declarations live in [`kvnloo/z0`](https://github.com/kvnloo/z0).**
z0archy compiles those declarations together with implementation evidence from exact Git refs and local worktrees. It does not silently promote observations into canonical truth.

The presentation engine is adapted from Yohei Nakajima's MIT-licensed [`graphcon-deck`](https://github.com/kvnloo/graphcon-deck). ActiveGraph is the temporal substrate for content-addressed architecture history: semantic graph states are persisted as event-sourced runs while z0archy's stable `z0://` identities remain canonical within each run.

## World model

The semantic graph distinguishes installable **components**, execution **harnesses**, reusable **mechanisms**, named **interfaces**, install **profiles**, promotion/history **lifecycles**, implementation **repositories**, exact **repo refs**, source **artifacts**, information **representations**, and epistemic **EvidenceDependency** claims. Nodes and relations carry provenance.

```text
kvnloo/z0 -> declared semantics -> canonical graph IR
                                 /              \
                       GitHub ref              local worktree
                           \                    /
                            implemented evidence
                                     |
                            virtual architecture
                                     |
                             graphcon-deck view
```

## Exact-ref architecture

Branch/worktree selection is no longer tooltip-only. For each selected repository version, z0archy inventories the selected Git tree once and compiles a loss-aware structural projection rather than copying every file into the graph.

The projection materializes:

- explicit `zer0.component.yaml` plus architecture/system/agent docs;
- every bounded package manifest across npm, Python, Cargo and Go monorepos;
- internal package-to-package dependency edges;
- schemas and API-contract artifacts;
- GitHub Actions workflows;
- a compressed test surface; and
- one repository-structure node retaining file counts, byte counts, top-level/extension distributions, tree truncation state and the source-files-per-semantic-node compression ratio.

GitHub tree inventories are keyed by immutable commit SHA and persisted under the same Actions cache as ref evidence. Raw file bodies still use `raw.githubusercontent.com`, so after the one tree inventory call, architecture-bearing content does not consume REST/GraphQL request budget.

The compiler still refuses to pretend arbitrary source-code imports are architectural truth. Import/call-graph analyzers can be added as a lower-confidence representation on the same exact-ref contract rather than silently promoting inferred edges.

## Hosted mode

GitHub Pages compiles the z0 registries, batches branch discovery through GraphQL, resolves branches to immutable SHAs, and materializes cached evidence packs from raw Git content. Both GraphQL responses and immutable ref evidence persist through Actions cache. Ordinary visitors make no authenticated GitHub API calls.

Selecting a GitHub branch opens an implemented-evidence graph scene for that exact commit rather than merely changing a label.

## Local mode

```bash
python -m pip install -r requirements.txt
python scripts/generate_graph.py
python scripts/generate_deck.py
python scripts/serve.py --workspace ~/src/zer0
```

The server discovers repositories and Git worktrees read-only. Each worktree has a content-addressed evidence identity derived from HEAD, path, upstream state and the actual bytes of dirty/untracked files. Unchanged worktrees reuse their compiled evidence pack instead of being re-introspected every poll. Dirty edits create a new evidence key immediately, including repeated edits while Git status remains simply "modified". The browser polls local state and swaps to the new exact worktree evidence when that key changes.

## Observed runtime world

Local z0archy can overlay runtime evidence without making runtime logs part of canonical architecture truth.

```bash
python scripts/serve.py --workspace ~/src/zer0 \
  --tokenomics-events ~/.local/share/tokenomics/events.jsonl \
  --agenttrace-report ~/tmp/agenttrace-overview.json \
  --aodl-document ~/tmp/orchestration.json
```

If `~/.local/share/tokenomics/events.jsonl` exists, `serve.py` discovers it automatically. Runtime inputs are fingerprinted and recompiled only when their files change.

The runtime compiler is intentionally **metadata-only**:

- Tokenomics events preserve trace/span identity, harness/model, tokens, measured economics, latency, context pressure and verification outcome.
- AgentTrace reports preserve session/source/model/health/time/token/cost metadata.
- AODL keeps intent graph, compiled plan and observed graph as separate objects and preserves structural topology/authority metadata.
- prompt/completion text, arbitrary message/content fields, tool arguments/results, secrets and arbitrary free-form payloads are excluded from the generated graph.

The browser exposes an **runtime** scene only when local runtime evidence exists. Trace/session/orchestration summaries are the high-level compression layer; individual operations and topology nodes live at deeper semantic levels. Observed nodes link back to canonical harnesses and information representations when those identities exist.

Standalone compilation is also available:

```bash
python scripts/compile_runtime_evidence.py \
  --tokenomics-events events.jsonl \
  --agenttrace-report agenttrace-overview.json \
  --aodl-document orchestration.json
```

`generated/runtime-evidence.json` is gitignored and is never produced by the public Pages workflow.

## Virtual multi-repo snapshots

Selections are portable JSON:

```json
{
  "version": 1,
  "repos": {
    "kvnloo/tokenomics": {"source": "github", "ref": "master"},
    "kvnloo/z0intelligence": {"source": "github", "ref": "feature/example"}
  }
}
```

Compile and compare:

```bash
python scripts/compile_snapshot.py --selection selection.json --output generated/virtual-graph.json
python scripts/diff_snapshots.py old.json new.json
```

Local selections use repeatable `--local-root owner/repo=/path/to/worktree`. Structural diffs report added, removed, and changed semantic nodes and relations.

## Information + epistemic planes

`registry/representations.yaml` makes the semantic data plane visible: raw context, addresses, ObservationPacks, compiled decision state, plans, observed topology, receipts and measurements can be graphed independently from the services that carry them.

`registry/evidence_dependencies.yaml` turns important relationships into inspectable claims. Each EvidenceDependency can preserve required evidence, invariants, invalidators, abstention conditions, confidence, and fastest/fallback retrieval paths. Required evidence references are first-class nodes rather than comments on an edge.

```bash
python scripts/lint_graph.py generated/graph.json --fail-on error
```

The linter fails unresolved evidence endpoints and structurally unverifiable claims while reporting weaker architecture-quality warnings separately.

## Profile, truth and lint lenses

Install profiles are executable graph lenses rather than documentation labels. Selecting `minimal`, `core`, `personal`, `desktop`, `compute`, `research` or `full` keeps the selected components and their nearby contracts, harnesses, mechanisms, repositories and evidence legible while dimming unrelated topology. Profile inheritance is resolved from the current semantic world, including historical and virtual worlds.

The truth lens can isolate **declared**, **implemented** or **derived** evidence. Dynamic exact-ref evidence is tagged implemented; virtual-composition nodes are tagged derived.

Pages also publishes `generated/lint.json`. The lint panel surfaces canonical provenance, unresolved EvidenceDependency, interface-provider and implementation-quality findings directly in the explorer rather than leaving them only in CI output.

## Virtual multi-repo architecture

The **ref matrix** composes one derived Zer0 world from immutable Git refs across every repository represented in the graph.

For installable components, “canonical” means the exact commit SHA declared by `kvnloo/z0`, even when the configured branch has advanced. Repositories that z0 references semantically but does not pin are labeled **un-pinned** and use the GitHub default branch only as an observational fallback.

Applying the matrix loads the precompiled evidence pack for every selected immutable commit, merges those packs over the declared world model, and compares selected implementation evidence against canonical evidence where a declared pin exists. The resulting virtual graph becomes the active world for question-conditioned MOCs.

The selection can be copied as a portable JSON manifest. Applied GitHub selections are URL-addressable with `virtual=1` and `v.<repo>=<ref>` parameters.

## Semantic zoom

The whole-world view uses semantic zoom rather than geometric scaling alone. Each graph node carries an abstraction depth. As the camera moves closer, z0archy progressively reveals:

```text
logic
  → concepts
    → important detail
      → deep detail
        → source evidence
```

Components and mechanism families survive the strongest compression. Harnesses, mechanisms, representations, interfaces, repositories, evidence claims, lifecycle states and source evidence appear progressively. Explicitly opening a focused scene or MOC overrides compression and shows that view in full.

## Dynamic Maps of Content

The canonical world model can be recompiled into a purpose-specific map in the browser. Enter a question such as `context compression`, `provider routing`, or `why is this evidence trusted`. The MOC compiler scores conceptual matches and then expands through typed graph proximity under a bounded node budget, preserving nearby mechanisms, representations, contracts and evidence instead of returning a flat search list.

MOCs are URL-addressable through `?moc=...`. When architecture history is active, the MOC is compiled from that historical graph snapshot rather than the current graph.

## ActiveGraph architecture history

Canonical semantic states are content-addressed before being recorded. Rebuilding an unchanged graph reuses the same ActiveGraph run; a changed graph creates a new run linked to the previous architecture state.

```bash
python scripts/record_history.py generated/graph.json
```

The build keeps the ActiveGraph SQLite event store under `.cache/`, stores the complete semantic graph in ActiveGraph's snapshot sidecar, and exports static replayable snapshots to `generated/history/` plus `generated/history-index.json`. Historical graphcon-deck documents are precompiled into `generated/history-decks/`, and the top-bar history selector can jump between live and prior semantic states without a backend. Live Git/ref controls are locked while viewing history so present-day observations cannot contaminate an older architecture state.

## GitHub API budget

The GitHub layer builds on GraphQL pagination + SQLite ingestion ideas previously used in `kvnloo/gh-contrib-archive`, adding deterministic query cache keys, batching, explicit rate-limit accounting, stale fallback, immutable commit-keyed evidence, one-call-per-new-SHA Git tree inventories, and Actions cache persistence.

## Validation

```bash
python -m unittest discover -s tests -v
python scripts/validate_graph.py generated/graph.json
python scripts/lint_graph.py generated/graph.json --fail-on error
python scripts/validate_deck.py deck.json
node --check sourcebar.js
```

Fixtures cover the richer semantic ontology, virtual ref compilation, structural diff, and a real multi-worktree Git fixture.

## Authority boundary

z0archy owns graph compilation, observation, provenance, comparison and presentation. It does not own the underlying architectural declaration, runtime measurements, research evidence, or implementation facts.

See `docs/ARCHITECTURE.md`, `AGENTS.md`, `NOTICE.md`, and `LICENSE`.

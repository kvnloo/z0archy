# z0archy

A dynamic, zoomable architecture explorer and semantic world model for the Zer0 ecosystem.

**Canonical architecture declarations live in [`kvnloo/z0`](https://github.com/kvnloo/z0).**
z0archy compiles those declarations together with implementation evidence from exact Git refs and local worktrees. It does not silently promote observations into canonical truth.

The presentation engine is adapted from Yohei Nakajima's MIT-licensed [`graphcon-deck`](https://github.com/kvnloo/graphcon-deck). ActiveGraph remains the planned temporal/event substrate for historical reconstruction and fork/diff once the source model is stable.

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

Branch/worktree selection is no longer tooltip-only. For each selected repository version, z0archy currently probes a bounded evidence-preserving surface:

- `zer0.component.yaml`
- `ARCHITECTURE.md`
- `README.md`
- `AGENTS.md`
- `package.json`, `pyproject.toml`, and `Cargo.toml`

Artifacts are hashed and attached to the exact repo-ref node with `implemented` provenance. Package identities and explicit Zer0 manifests become semantic nodes.

This first compiler intentionally does **not** claim to infer every package, import, schema, test, or runtime dependency yet. Those analyzers can append evidence onto the same stable repo/ref contract.

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

The server discovers repositories and Git worktrees read-only. Each worktree has its own evidence identity even when worktrees share a HEAD. The compiler reads live filesystem files, so dirty architecture/package documents are represented without committing them. The browser polls local state and rebuilds selected evidence when hashes change.

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

## GitHub API budget

The GitHub layer builds on GraphQL pagination + SQLite ingestion ideas previously used in `kvnloo/gh-contrib-archive`, adding deterministic query cache keys, batching, explicit rate-limit accounting, stale fallback, immutable commit-keyed evidence, and Actions cache persistence.

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

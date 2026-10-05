# Unified memory virtual snapshots

These presets expose **draft exact-ref evidence**. They are not canonical Zer0 architecture and they deliberately do not merge incompatible z0intelligence branches into a fictional combined state.

## Ledger + OptMem implementation stack

`selections/unified-memory-ledger-optmem-v0.json` selects:

- z0intelligence `feat/memory-optmem-tree-v0`, which is stacked on the event-ledger work;
- OptMem `main` as the temporal projection substrate;
- Hermes LCM `main` as a separate recoverable context-engine implementation;
- z0evals `main` for the frozen Unified Memory v0 evaluation surface.

Compile it with:

```bash
python scripts/compile_snapshot.py \
  --selection selections/unified-memory-ledger-optmem-v0.json \
  --output generated/unified-memory-ledger-optmem-v0.json
```

The selected z0intelligence branch still carries the older `zer0.repo.yaml`. Therefore new ledger/OptMem files are implementation evidence, but z0archy must **not invent new subsystem nodes** until that branch explicitly declares them.

## Lifelong-memory contract preview

`selections/unified-memory-contract-v1.json` selects the separate
`feat/memory-contract-v1-66-preview` branch plus z0evals.

```bash
python scripts/compile_snapshot.py \
  --selection selections/unified-memory-contract-v1.json \
  --output generated/unified-memory-contract-v1.json
```

That preview branch currently has no `zer0.repo.yaml`. Its files/docs remain raw exact-ref evidence only.

## Invariant

Canonical merged truth remains the z0intelligence unified-memory evidence path / ContextPacket contract on the ref pinned by `kvnloo/z0`. These presets exist to inspect work **before promotion**, not to promote it.

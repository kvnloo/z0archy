# AgentWeb + Emma + z0 virtual snapshot

This preset is a **derived downstream experiment**, not canonical Zer0 architecture.

```bash
python scripts/compile_snapshot.py \
  --selection selections/agentweb-emma-z0-v0.json \
  --output generated/agentweb-emma-z0-v0.json
```

It composes the experimental branches for z0, AODL, AgentWeb, z0intelligence and z0evals so the exact-ref implementation manifests and registry changes can be inspected together.

Rules:

- every selected repository is under `kvnloo/`;
- no selected ref is a default/stable branch;
- changing this preset cannot promote canonical z0 truth;
- promotion decisions remain outside z0archy;
- missing/unresolved exact-ref evidence must remain visible rather than being synthesized.

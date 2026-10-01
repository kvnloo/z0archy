# First-party Zer0 core stack

This is an orientation layer for the first systems designed inside Zer0. It is **not**
a second architecture registry. Canonical identities and cross-system relations live in
`kvnloo/z0`; exact implementation structure lives in each repository's
`zer0.repo.yaml`.

## Core loop

```text
AODL intent / Pi / Gamma
        |
        v
z0intelligence
  +-- provenance-backed context resolution ----> ContextPacket
  +-- bounded decision runtime ----------------> DecisionReceipt
  +-- harness adapters
  +-- Kubernetes hermes-lab lane
        |
        v
observed execution / verification
        |
        +-----------------------> Tokenomics
        |                           |
        |                           v
        |                    measured economics
        |                           |
        v                           v
      z0evals <--------------- frozen studies
        |
        v
independent evidence
        |
        v
Evolution Lab
  +-- locked corpora / splits
  +-- specialist search
  +-- ABAB / Pareto / MAP-Elites
  +-- promotion evidence
        |
        v
promoted specialist artifact
        |
        +-----------------------> z0intelligence runtime
```

## Ownership boundaries

### z0intelligence

Owns the personal intelligence implementation: source-backed context resolution,
bounded decision backends, specialist/routine runtime, auditable receipts, harness
adapter contracts, and its deployment topology.

It does **not** become the source memory database, harness runtime, experiment
promotion authority, Tokenomics measurement kernel, or AODL ontology.

The unified-memory design is represented as the
`unified-memory-evidence-path` mechanism and `context-packet` representation.
Retrieval, model-visible injection, answer support, and verification stay distinct.

### Kubernetes lane

The first Kubernetes topology is an implementation subsystem of z0intelligence rather
than a new top-level product. The `hermes-lab` lane keeps z0int decision/dispatch authority and local model control
host-side while exposing a hardened in-cluster executor through the z0intelligence
service boundary. Provider credentials may be explicitly scoped into that executor as
Kubernetes secrets; the architecture must not claim that all credentials remain host-only.

### Evolution Lab

Owns experiment search, locked corpora/splits, candidate evolution, DAgger,
Pareto/MAP-Elites comparison, and promotion evidence. Production execution stays in
z0intelligence. Frozen public evaluation stays in z0evals.

### AODL

Owns the portable orchestration contract: intent graph, policy `Pi`, constraints and
authority `Gamma`, fail-closed validation, and runtime-specific compilation profiles.
It is not a scheduler, model trainer, measurement system, or provider allocator.

### Tokenomics

Owns vendor-neutral measurement semantics for usage, context economics, latency, cost,
quota, experiments, attribution, completeness, and independently verified outcomes.
JSONL remains durable offline truth; OTLP is transport.

### z0evals

Owns frozen study contracts and publication evidence. Unified Memory v0 keeps retrieval,
injection, answer support, provenance, abstention, idempotency, supersession, latency,
and context cost separable so a configured index cannot masquerade as working memory.

## How z0archy resolves this

1. `kvnloo/z0` supplies canonical components, mechanisms, interfaces,
   representations, evidence dependencies, and suite roles.
2. Canonical component refs point to immutable commits.
3. Each selected repository ref may contribute `zer0.repo.yaml` subsystem structure.
4. z0archy resolves only manifest references that already exist canonically.
5. Virtual worlds can swap refs without mutating canonical truth.
6. Runtime evidence remains observational and cannot silently rewrite the declared map.

The result is one graph that can zoom from the first-party control loop down to the
actual context resolver, decision backends, Kubernetes manifests, experiment machinery,
schemas, tests, and frozen study surfaces while preserving provenance.

## Adjacent active repository surfaces

These repositories are part of the current Zer0 repository map without being promoted
to new installable core components:

- **Agent Orchestrator** — orchestration runtime experiments around z0intelligence
  decisions/outcomes and AODL contracts.
- **OptMem** — memory research substrate used by z0intelligence branches for temporal
  projection and bounded-cover experiments; it does not own canonical memory truth.
- **Bend** — proof-oriented compilation substrate explored for enforceable AODL /
  z0intelligence contracts.
- **AgentWeb / Emma integration** — downstream harness surface for typed decisions,
  personal context, and orchestration experiments.
- **SoL-Pi OMP** — OMP-focused port/packaging of reusable SoL-Pi efficiency mechanisms.

Draft experiment branches remain non-canonical. z0archy indexes them as selectable exact
refs while `kvnloo/z0` remains the authority for canonical repository membership and
cross-system semantics.

## Current z0intelligence decision truth

The current production-facing decision story is no longer the early NanoJev prototype:

- **TypeSafe Jev 1.13.0** is the reference verifier for the registered evidence-sufficiency capability.
- **Laya 421M** is the resident local typed-decision fast path; broader automatic verification eligibility is still experimental.
- **OpenJev**, Decider-2B, Julia-1, and image-decision backends remain benchmark / experimental surfaces unless a registered capability explicitly promotes them.
- **NanoJev is legacy-only**, retained for reproducibility rather than as the verification default.
- Deterministic legality, permissions, budgets, replay/conflict protection, and dispatch authority are compiled before learned choice.

This distinction matters in z0archy: a backend existing in the repository does not imply authority to route or execute.

## Unified memory: merged core vs active lab

Merged canonical behavior remains the **unified-memory evidence path**: explicit information
needs resolve into provenance-bearing ContextPackets / StatePacket-style bounded evidence,
with retrieval, model-visible injection, answer support, and verification kept separate.

The newer memory program is active but **not all merged into z0intelligence master yet**.
Its intended split is:

```text
EPISODIC   EventLog + OptMem temporal projection
RETRIEVAL  FTS5 + AgentsView
SEMANTIC   TencentDB L1/L2/L3
WORKING    StatePacket / query-time compiler
PROCEDURAL verified routine compiler
```

z0archy therefore shows this as a lab view. Exact branch/PR evidence must be selected before
those unmerged layers are treated as implementation truth.

# Architecture

## Responsibility

`z0archy` is the interactive projection and observation surface for the Zer0
architecture. It does not own the architecture.

Canonical cross-system declarations live in `kvnloo/z0`. Implementation facts live
in their component repositories. GitHub and local Git state are observations.

## Truth classes

z0archy keeps source classes explicit:

| Class | Meaning | Authority |
| --- | --- | --- |
| declared | component boundaries, profiles, interfaces, maturity | `kvnloo/z0` |
| implemented | facts discovered at a repository ref | component repository |
| observed | branch heads, worktrees, runtime state | originating system |
| historical | prior snapshots/events | event/provenance store |
| derived | graph/layout analysis calculated by z0archy | z0archy, with inputs attached |

A lower-authority observation may reveal drift, but it never silently rewrites a
higher-authority declaration.

## Graph IR

`generated/graph.json` is the semantic intermediate representation.

Stable identities use URI-like IDs:

```text
z0://component/tokenomics
z0://repo/kvnloo/tokenomics
z0://interface/tokenomics.event.v0
z0://profile/core
```

Nodes contain provenance. Edges represent typed relationships such as
`depends_on`, `integrates_with`, `provides`, `consumes`, and `includes`.

The browser's graphcon-deck document is generated from this IR. Spatial positions and
camera scenes are presentation concerns and are not architecture facts.

## Source providers

### Canonical registry

`z0archy_core.registry` reads the four canonical z0 registries from either a local z0
checkout or a Git ref.

### GitHub

`z0archy_core.github` discovers branch heads using GraphQL. Repositories are batched
into one query in the common case. Pagination is per-repository only when a repository
has more than 100 branches.

The query cache is SQLite-backed and keyed by normalized query + variables. Scheduled
Pages builds restore that cache through GitHub Actions cache.

### Local Git

`z0archy_core.local_git` uses Git plumbing rather than directory names for identity.
A repository and a checkout/worktree are separate concepts. All worktrees reported by
`git worktree list --porcelain` remain attached to the same normalized remote identity.

The local web server updates known Git state frequently but re-runs filesystem discovery
less often.

## Cloud and local parity

Both modes feed the same semantic graph and differ only in evidence providers:

```text
                     SourceProvider
                     /            \
              local Git          GitHub
                  \                /
                   observation model
                         |
                  canonical graph IR
                         |
                  graphcon-deck view
```

A branch selector therefore selects evidence for a repository rather than mutating or
checking out that branch.

## ActiveGraph seam

ActiveGraph is the intended temporal substrate, not the authority for Zer0 architecture.

The z0archy ontology maps naturally to ActiveGraph objects and relations:

- graph IR nodes → typed objects;
- graph IR edges → typed relations;
- Git/ref/worktree discoveries → observation events;
- canonical rebuilds → architecture snapshot events; and
- later runtime overlays → custom events carrying originating-system provenance.

This repository deliberately does not require ActiveGraph in the first source-provider
slice. The graph/source contracts are deterministic first, so an ActiveGraph adapter can
event-source the same observations without changing their meaning or making the static
Pages build depend on a runtime service.

## Failure boundaries

- API exhaustion must degrade to cache or fail explicitly, never fabricate refs.
- Missing local repositories are absence of observation, not absence of architecture.
- A dirty worktree is reported, never modified.
- z0archy never checks out, rebases, resets, commits, or pushes source repositories.
- Generated graph edges must point to existing stable IDs.
- Browser failure to load optional Git/local overlays must leave the canonical deck usable.

## Next layers

The source model is designed to accept deeper implemented evidence from selected refs,
semantic zoom from system → component → interface → repository, architecture diffs
between ref sets, and ActiveGraph-backed historical replay without changing the canonical
ownership boundary.

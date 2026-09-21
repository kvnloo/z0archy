from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from .cache import SqliteJsonCache

GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass(frozen=True)
class RateLimit:
    cost: int | None = None
    remaining: int | None = None
    reset_at: str | None = None


class GitHubGraphQLClient:
    def __init__(
        self,
        token: str | None = None,
        *,
        cache_path: str = ".cache/github.sqlite3",
        ttl_seconds: int = 900,
        min_remaining: int = 25,
        user_agent: str = "z0archy",
    ):
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.cache = SqliteJsonCache(cache_path)
        self.ttl_seconds = ttl_seconds
        self.min_remaining = min_remaining
        self.user_agent = user_agent
        self.last_rate_limit = RateLimit()

    def close(self) -> None:
        self.cache.close()

    def query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        key = self.cache.request_key(query, variables)
        cached = self.cache.get(key)
        if cached is not None:
            self._capture_rate_limit(cached)
            return cached

        stale = self.cache.get(key, allow_stale=True)
        if not self.token:
            if stale is not None:
                self._capture_rate_limit(stale)
                return stale
            raise RuntimeError("GH_TOKEN or GITHUB_TOKEN is required when the GitHub cache is cold")

        if self.last_rate_limit.remaining is not None and self.last_rate_limit.remaining < self.min_remaining:
            if stale is not None:
                return stale
            raise RuntimeError(
                f"GitHub GraphQL budget is low ({self.last_rate_limit.remaining} remaining; "
                f"resets {self.last_rate_limit.reset_at})"
            )

        req = urllib.request.Request(
            GRAPHQL_URL,
            method="POST",
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError):
            if stale is not None:
                self._capture_rate_limit(stale)
                return stale
            raise
        if payload.get("errors"):
            if stale is not None:
                self._capture_rate_limit(stale)
                return stale
            msg = "; ".join(str(e.get("message", e)) for e in payload["errors"])
            raise RuntimeError(f"GitHub GraphQL error: {msg}")
        self._capture_rate_limit(payload)
        self.cache.put(key, payload, self.ttl_seconds)
        return payload

    def _capture_rate_limit(self, payload: dict[str, Any]) -> None:
        rl = (payload.get("data") or {}).get("rateLimit") or {}
        self.last_rate_limit = RateLimit(
            cost=rl.get("cost"), remaining=rl.get("remaining"), reset_at=rl.get("resetAt")
        )


def _repo_parts(repo: str) -> tuple[str, str]:
    owner, sep, name = repo.partition("/")
    if not sep or not owner or not name:
        raise ValueError(f"expected owner/name repository, got {repo!r}")
    return owner, name


def fetch_branch_index(
    repos: Iterable[str], client: GitHubGraphQLClient, *, batch_size: int = 20
) -> dict[str, Any]:
    """Fetch branch heads with one GraphQL call per batch in the common case.

    Repositories with >100 branches are paginated individually after the first batch.
    """
    ordered = sorted(dict.fromkeys(repos))
    result: dict[str, Any] = {}
    for offset in range(0, len(ordered), batch_size):
        batch = ordered[offset : offset + batch_size]
        variables: dict[str, Any] = {}
        defs: list[str] = []
        fields: list[str] = []
        alias_to_repo: dict[str, str] = {}
        for i, repo in enumerate(batch):
            owner, name = _repo_parts(repo)
            alias = f"r{i}"
            alias_to_repo[alias] = repo
            variables[f"owner{i}"] = owner
            variables[f"name{i}"] = name
            defs.extend([f"$owner{i}: String!", f"$name{i}: String!"])
            fields.append(
                f"""
                {alias}: repository(owner: $owner{i}, name: $name{i}) {{
                  nameWithOwner
                  defaultBranchRef {{
                    name
                    target {{ ... on Commit {{ oid committedDate }} }}
                  }}
                  refs(refPrefix: "refs/heads/", first: 100,
                       orderBy: {{field: TAG_COMMIT_DATE, direction: DESC}}) {{
                    pageInfo {{ hasNextPage endCursor }}
                    nodes {{ name target {{ ... on Commit {{ oid committedDate }} }} }}
                  }}
                }}
                """
            )
        query = "query(" + ", ".join(defs) + ") {\n" + "\n".join(fields) + "\nrateLimit { cost remaining resetAt }\n}"
        payload = client.query(query, variables)
        data = payload.get("data") or {}
        for alias, repo in alias_to_repo.items():
            node = data.get(alias)
            if not node:
                result[repo] = {"error": "repository unavailable", "branches": []}
                continue
            refs = node.get("refs") or {"nodes": [], "pageInfo": {}}
            branches = [_branch_row(x) for x in (refs.get("nodes") or [])]
            page = refs.get("pageInfo") or {}
            if page.get("hasNextPage"):
                branches.extend(_paginate_repo_branches(repo, page.get("endCursor"), client))
            default = node.get("defaultBranchRef") or {}
            result[repo] = {
                "defaultBranch": default.get("name"),
                "defaultHead": _target_oid(default.get("target")),
                "branches": _dedupe_branches(branches),
            }
    return result


def _paginate_repo_branches(repo: str, cursor: str | None, client: GitHubGraphQLClient) -> list[dict[str, Any]]:
    owner, name = _repo_parts(repo)
    rows: list[dict[str, Any]] = []
    query = """
      query($owner: String!, $name: String!, $cursor: String) {
        repository(owner: $owner, name: $name) {
          refs(refPrefix: "refs/heads/", first: 100, after: $cursor,
               orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
            pageInfo { hasNextPage endCursor }
            nodes { name target { ... on Commit { oid committedDate } } }
          }
        }
        rateLimit { cost remaining resetAt }
      }
    """
    while cursor:
        payload = client.query(query, {"owner": owner, "name": name, "cursor": cursor})
        refs = (((payload.get("data") or {}).get("repository") or {}).get("refs") or {})
        rows.extend(_branch_row(x) for x in (refs.get("nodes") or []))
        page = refs.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
    return rows


def _target_oid(target: Any) -> str | None:
    return target.get("oid") if isinstance(target, dict) else None


def _branch_row(node: dict[str, Any]) -> dict[str, Any]:
    target = node.get("target") or {}
    return {
        "name": node.get("name"),
        "oid": target.get("oid"),
        "committedAt": target.get("committedDate"),
    }


def _dedupe_branches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        name = row.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(row)
    return out

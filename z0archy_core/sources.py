from __future__ import annotations

import hashlib
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Protocol


class SourceProvider(Protocol):
    kind: str

    def read_text(self, repo: str, ref: str, path: str) -> str | None:
        """Return UTF-8 text at repo/ref/path, or None when the path is absent."""

    def resolve_ref(self, repo: str, ref: str) -> str:
        """Return a stable commit identity when available."""


class GitHubRawSource:
    """Read public GitHub blobs without consuming REST/GraphQL request budget."""

    kind = "github"

    def __init__(self, *, timeout: int = 20, user_agent: str = "z0archy"):
        self.timeout = timeout
        self.user_agent = user_agent

    def read_text(self, repo: str, ref: str, path: str) -> str | None:
        owner, name = _repo_parts(repo)
        safe_ref = urllib.parse.quote(ref, safe="/._-")
        safe_path = "/".join(urllib.parse.quote(p, safe="._-") for p in path.split("/"))
        url = f"https://raw.githubusercontent.com/{owner}/{name}/{safe_ref}/{safe_path}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def resolve_ref(self, repo: str, ref: str) -> str:
        # Raw content does not expose the resolved SHA. Keep an explicit, stable
        # provider-local identity; callers may enrich it from the GitHub branch index.
        return f"github:{repo}@{ref}"


class LocalGitSource:
    """Read one local Git checkout/worktree without mutating it."""

    kind = "local"

    def __init__(self, roots: dict[str, str | Path]):
        self.roots = {repo: Path(path).expanduser().resolve() for repo, path in roots.items()}

    def _root(self, repo: str) -> Path:
        if repo not in self.roots:
            raise KeyError(f"no local root configured for {repo}")
        return self.roots[repo]

    def read_text(self, repo: str, ref: str, path: str) -> str | None:
        root = self._root(repo)
        if ref == "WORKTREE":
            candidate = (root / path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                return None
            if not candidate.is_file():
                return None
            try:
                return candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return None
        proc = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{path}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode:
            return None
        return proc.stdout

    def resolve_ref(self, repo: str, ref: str) -> str:
        root = self._root(repo)
        target = "HEAD" if ref == "WORKTREE" else ref
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", target],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return proc.stdout.strip()


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_parts(repo: str) -> tuple[str, str]:
    owner, sep, name = repo.partition("/")
    if not sep or not owner or not name:
        raise ValueError(f"expected owner/name repository, got {repo!r}")
    return owner, name

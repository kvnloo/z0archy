from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Protocol


_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")


class SourceProvider(Protocol):
    kind: str

    def read_text(self, repo: str, ref: str, path: str) -> str | None:
        """Return UTF-8 text at repo/ref/path, or None when the path is absent."""

    def resolve_ref(self, repo: str, ref: str) -> str:
        """Return a stable commit identity when available."""

    def list_tree(self, repo: str, ref: str) -> dict[str, Any]:
        """Return a bounded-neutral tree inventory for one repository ref."""


class GitHubRawSource:
    """Read public GitHub blobs and trees while caching immutable tree inventories.

    Raw blob reads avoid REST/GraphQL budget entirely. Tree enumeration uses one REST
    call per previously unseen immutable commit and persists the response on disk so
    future Pages builds can reuse it through the Actions cache.
    """

    kind = "github"

    def __init__(
        self,
        *,
        timeout: int = 20,
        user_agent: str = "z0archy",
        token: str | None = None,
        tree_cache_dir: str | Path = ".cache/ref-evidence/trees",
    ):
        self.timeout = timeout
        self.user_agent = user_agent
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.tree_cache_dir = Path(tree_cache_dir)

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
        except UnicodeDecodeError:
            return None

    def resolve_ref(self, repo: str, ref: str) -> str:
        # Raw content does not expose the resolved SHA. Callers that already have the
        # branch index should pass resolved_ref into inspect_repository.
        return f"github:{repo}@{ref}"

    def list_tree(self, repo: str, ref: str) -> dict[str, Any]:
        immutable = bool(_SHA40.fullmatch(ref))
        cache_path = self._tree_cache_path(repo, ref) if immutable else None
        if cache_path and cache_path.is_file():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        owner, name = _repo_parts(repo)
        safe_ref = urllib.parse.quote(ref, safe="")
        url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{safe_ref}?recursive=1"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset = response.headers.get("X-RateLimit-Reset")
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 409):
                return {
                    "entries": [],
                    "truncated": False,
                    "error": f"github_tree_http_{exc.code}",
                }
            raise

        entries = []
        for row in body.get("tree") or []:
            path = row.get("path")
            kind = row.get("type")
            if not path or kind not in {"blob", "tree"}:
                continue
            entries.append({
                "path": str(path),
                "type": kind,
                "oid": row.get("sha"),
                "size": row.get("size"),
                "mode": row.get("mode"),
            })
        result = {
            "entries": entries,
            "truncated": bool(body.get("truncated")),
            "treeOid": body.get("sha"),
            "rateLimit": {
                "remaining": int(remaining) if remaining and remaining.isdigit() else None,
                "resetEpoch": int(reset) if reset and reset.isdigit() else None,
            },
        }
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
        return result

    def _tree_cache_path(self, repo: str, ref: str) -> Path:
        owner, name = _repo_parts(repo)
        return self.tree_cache_dir / owner / name / f"{ref.lower()}.json"


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

    def list_tree(self, repo: str, ref: str) -> dict[str, Any]:
        root = self._root(repo)
        if ref == "WORKTREE":
            proc = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z", "-c", "-o", "--exclude-standard"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            paths = sorted(set(p.decode("utf-8", errors="surrogateescape") for p in proc.stdout.split(b"\0") if p))
            entries = []
            for path in paths:
                candidate = root / path
                if not candidate.is_file():
                    continue
                try:
                    size = candidate.stat().st_size
                except OSError:
                    size = None
                entries.append({"path": path, "type": "blob", "oid": None, "size": size, "mode": None})
            return {"entries": entries, "truncated": False, "worktree": True}

        proc = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "-l", "-z", ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        entries: list[dict[str, Any]] = []
        for raw in proc.stdout.split(b"\0"):
            if not raw:
                continue
            text = raw.decode("utf-8", errors="surrogateescape")
            meta, sep, path = text.partition("\t")
            if not sep:
                continue
            parts = meta.split()
            if len(parts) < 4:
                continue
            mode, kind, oid, size_raw = parts[:4]
            if kind != "blob":
                continue
            entries.append({
                "path": path,
                "type": "blob",
                "oid": oid,
                "size": int(size_raw) if size_raw.isdigit() else None,
                "mode": mode,
            })
        return {"entries": entries, "truncated": False, "worktree": False}


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_parts(repo: str) -> tuple[str, str]:
    owner, sep, name = repo.partition("/")
    if not sep or not owner or not name:
        raise ValueError(f"expected owner/name repository, got {repo!r}")
    return owner, name

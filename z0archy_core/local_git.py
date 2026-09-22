from __future__ import annotations

import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", ".cache", "dist", "build", "__pycache__"}


def normalize_remote(url: str) -> str | None:
    value = url.strip()
    patterns = [
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?$",
        r"^https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        m = re.match(pattern, value)
        if m:
            return m.group(1).removesuffix(".git")
    return None


def discover_git_roots(roots: Iterable[str | Path]) -> list[Path]:
    found: set[Path] = set()
    for raw in roots:
        root = Path(raw).expanduser().resolve()
        if not root.exists():
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            p = Path(current)
            if (p / ".git").exists():
                found.add(p.resolve())
    return sorted(found)


def build_local_snapshot(roots: Iterable[str | Path]) -> dict[str, Any]:
    return build_local_snapshot_from_git_roots(discover_git_roots(roots))


def build_local_snapshot_from_git_roots(git_roots: Iterable[str | Path]) -> dict[str, Any]:
    repos: dict[str, dict[str, Any]] = {}
    visited_worktrees: set[str] = set()
    for raw_root in git_roots:
        root = Path(raw_root).expanduser().resolve()
        if not (root / ".git").exists():
            continue
        remote = _git(root, "remote", "get-url", "origin", check=False).strip()
        github_repo = normalize_remote(remote) if remote else None
        repo_id = github_repo or f"local:{hashlib.sha256(str(root).encode()).hexdigest()[:16]}"
        entry = repos.setdefault(repo_id, {"repo": github_repo, "roots": [], "worktrees": []})
        if str(root) not in entry["roots"]:
            entry["roots"].append(str(root))
        for wt in _worktrees(root):
            path = str(Path(wt["path"]).resolve())
            if path in visited_worktrees:
                continue
            visited_worktrees.add(path)
            wp = Path(path)
            status = _status(wp)
            path_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()[:10]
            head = wt.get("head") or "unknown"
            dirty_fingerprint = _worktree_fingerprint(wp, head, status)
            entry["worktrees"].append({
                **wt,
                **status,
                "path": path,
                "dirtyFingerprint": dirty_fingerprint,
                "evidenceKey": f"{head}-{path_hash}-{dirty_fingerprint[:12]}",
            })

    for entry in repos.values():
        entry["roots"].sort()
        entry["worktrees"].sort(key=lambda w: w["path"])
    return {
        "schemaVersion": "0.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "truthClass": "observed",
        "repositories": repos,
    }


def _git(path: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _worktrees(root: Path) -> list[dict[str, Any]]:
    text = _git(root, "worktree", "list", "--porcelain")
    blocks = [b for b in text.strip().split("\n\n") if b.strip()]
    out: list[dict[str, Any]] = []
    for block in blocks:
        row: dict[str, Any] = {"detached": False, "locked": False, "prunable": False}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                row["path"] = value
            elif key == "HEAD":
                row["head"] = value
            elif key == "branch":
                row["branch"] = value.removeprefix("refs/heads/")
            elif key == "detached":
                row["detached"] = True
            elif key == "locked":
                row["locked"] = True
            elif key == "prunable":
                row["prunable"] = True
        if row.get("path"):
            out.append(row)
    return out


def _dirty_paths(path: Path) -> tuple[list[str], bytes]:
    proc = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain=v2", "-z", "--untracked-files=all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    records = proc.stdout.split(b"\0")
    paths: list[str] = []
    skip_original = False
    for raw in records:
        if not raw:
            continue
        if skip_original:
            skip_original = False
            continue
        record = raw.decode("utf-8", errors="surrogateescape")
        if record.startswith("? "):
            paths.append(record[2:])
        elif record.startswith("1 "):
            parts = record.split(" ", 8)
            if len(parts) == 9:
                paths.append(parts[8])
        elif record.startswith("2 "):
            parts = record.split(" ", 9)
            if len(parts) == 10:
                paths.append(parts[9])
                skip_original = True
        elif record.startswith("u "):
            parts = record.split(" ", 10)
            if len(parts) == 11:
                paths.append(parts[10])
    return sorted(set(paths)), proc.stdout


def _worktree_fingerprint(path: Path, head: str, status: dict[str, Any]) -> str:
    dirty_paths, raw_status = _dirty_paths(path)
    digest = hashlib.sha256()
    digest.update(head.encode("utf-8"))
    digest.update(raw_status)
    digest.update(str(status.get("upstream") or "").encode("utf-8"))
    digest.update(str(status.get("ahead") or 0).encode("ascii"))
    digest.update(str(status.get("behind") or 0).encode("ascii"))
    for rel in dirty_paths:
        digest.update(rel.encode("utf-8", errors="surrogateescape"))
        candidate = path / rel
        try:
            stat = candidate.stat()
        except OSError:
            digest.update(b"<missing>")
            continue
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        if candidate.is_file() and stat.st_size <= 2 * 1024 * 1024:
            try:
                with candidate.open("rb") as handle:
                    while True:
                        chunk = handle.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
            except OSError:
                pass
    return digest.hexdigest()


def _status(path: Path) -> dict[str, Any]:
    out = _git(path, "status", "--porcelain=v2", "--branch", check=False)
    dirty = 0
    upstream = None
    ahead = behind = 0
    for line in out.splitlines():
        if line.startswith("# branch.upstream "):
            upstream = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            parts = line.split()
            for part in parts:
                if part.startswith("+"):
                    ahead = int(part[1:])
                elif part.startswith("-"):
                    behind = int(part[1:])
        elif line and not line.startswith("#"):
            dirty += 1
    return {"dirtyFiles": dirty, "upstream": upstream, "ahead": ahead, "behind": behind}

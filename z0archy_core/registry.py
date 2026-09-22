from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

FILES = {
    "components": "registry/components.yaml",
    "interfaces": "registry/interfaces.yaml",
    "profiles": "registry/profiles.yaml",
    "maturity": "registry/maturity.yaml",
}
OPTIONAL_FILES = {
    "harnesses": "registry/harnesses.yaml",
    "mechanisms": "registry/mechanisms.yaml",
    "representations": "registry/representations.yaml",
    "evidence_dependencies": "registry/evidence_dependencies.yaml",
    "lifecycles": "registry/lifecycles.yaml",
}


def load_registry(*, repo: str = "kvnloo/z0", ref: str = "main", local_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    all_files = {**FILES, **OPTIONAL_FILES}
    if local_root is not None:
        root = Path(local_root)
        for key, rel in all_files.items():
            path = root / rel
            if not path.exists() and key in OPTIONAL_FILES:
                out[key] = {}
                continue
            out[key] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return out

    for key, rel in all_files.items():
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{rel}"
        req = urllib.request.Request(url, headers={"User-Agent": "z0archy"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                out[key] = yaml.safe_load(response.read().decode("utf-8")) or {}
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and key in OPTIONAL_FILES:
                out[key] = {}
                continue
            raise
    return out

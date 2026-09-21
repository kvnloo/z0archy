from __future__ import annotations

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


def load_registry(*, repo: str = "kvnloo/z0", ref: str = "main", local_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if local_root is not None:
        root = Path(local_root)
        for key, rel in FILES.items():
            out[key] = yaml.safe_load((root / rel).read_text(encoding="utf-8")) or {}
        return out

    for key, rel in FILES.items():
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{rel}"
        req = urllib.request.Request(url, headers={"User-Agent": "z0archy"})
        with urllib.request.urlopen(req, timeout=30) as response:
            out[key] = yaml.safe_load(response.read().decode("utf-8")) or {}
    return out

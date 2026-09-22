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
    "lifecycles": "registry/lifecycles.yaml",
    "representations": "registry/representations.yaml",
    "evidence_dependencies": "registry/evidence_dependencies.yaml",
}


def _read_yaml(text: str) -> dict[str, Any]:
    return yaml.safe_load(text) or {}


def load_registry(
    *,
    repo: str = "kvnloo/z0",
    ref: str = "main",
    local_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load canonical z0 registries.

    New semantic dimensions are optional so z0archy can inspect historical z0 refs
    created before the richer ontology existed.
    """
    out: dict[str, dict[str, Any]] = {}
    if local_root is not None:
        root = Path(local_root)
        for key, rel in FILES.items():
            out[key] = _read_yaml((root / rel).read_text(encoding="utf-8"))
        for key, rel in OPTIONAL_FILES.items():
            path = root / rel
            out[key] = _read_yaml(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return out

    for key, rel in {**FILES, **OPTIONAL_FILES}.items():
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{rel}"
        req = urllib.request.Request(url, headers={"User-Agent": "z0archy"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                out[key] = _read_yaml(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if key in OPTIONAL_FILES and exc.code == 404:
                out[key] = {}
                continue
            raise
    return out

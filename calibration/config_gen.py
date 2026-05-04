"""Generate a temporary config.yaml from a base config + parameter overrides."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml


def generate(
    base_config_path: str | Path,
    params: dict[str, dict[str, float]],
    tmp_dir: Path | None = None,
) -> Path:
    """
    Write a temp config.yaml with weight/alpha overrides applied per plugin.

    Args:
        base_config_path: Path to the base YAML config.
        params: {plugin_name: {weight: float, alpha: float}}
        tmp_dir: Directory for the temp file (defaults to system tmp).

    Returns:
        Path to the written temp file (caller is responsible for deletion).
    """
    raw: dict = yaml.safe_load(Path(base_config_path).read_text())

    plugins_raw = raw.setdefault("plugins", {})
    for plugin_name, overrides in params.items():
        if plugin_name not in plugins_raw:
            continue
        if "weight" in overrides:
            plugins_raw[plugin_name]["weight"] = overrides["weight"]
        if "alpha" in overrides:
            plugins_raw[plugin_name]["alpha"] = overrides["alpha"]

    suffix = ".yaml"
    kw = {"dir": str(tmp_dir)} if tmp_dir is not None else {}
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, prefix="evoseer_abc_", **kw
    )
    yaml.dump(raw, fd)
    fd.close()
    return Path(fd.name)

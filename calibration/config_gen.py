"""Generate a temporary config.yaml from a base config + parameter overrides."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml


def _deep_update(target: dict, overrides: dict) -> None:
    """Recursively merge overrides into target in-place."""
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


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
    for name, overrides in params.items():
        if name == "rate_function":
            _deep_update(raw.setdefault("rate_function", {}), overrides)
        elif name in plugins_raw:
            _deep_update(plugins_raw[name], overrides)

    suffix = ".yaml"
    kw = {"dir": str(tmp_dir)} if tmp_dir is not None else {}
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, prefix="evoseer_abc_", **kw
    )
    config_path = Path(fd.name)

    # Give each calibration run its own output dir derived from the temp file name.
    output_dir = config_path.parent / config_path.stem
    raw.setdefault("recorder", {})["output_dir"] = str(output_dir)

    yaml.dump(raw, fd)
    fd.close()
    return config_path

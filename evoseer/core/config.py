"""YAML configuration loading and typed config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PluginConfig:
    """Configuration for a single FeaturePlugin instance."""

    name: str
    plugin_type: str                         # maps to a registered plugin class
    target: str                              # 'rate_function' | 'mutation_rate'
    category: str = "proliferative"         # 'proliferative' | 'deleterious'
    weight: float = 1.0
    alpha: float = 0.0                       # density-dependence exponent
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MutationStoreConfig:
    """Configuration for the MutationStore backend."""

    source: str = ":memory:"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MutationGeneratorConfig:
    """Configuration for the MutationGenerator."""

    generator_type: str = "uniform"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RateFunctionConfig:
    """Configuration for the RateFunction."""

    function_type: str = "weighted_sum"
    baseline_birth_rate: float = 0.5
    baseline_death_rate: float = 0.2
    carrying_capacity: float | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecorderConfig:
    """Configuration for the Recorder."""

    output_dir: Path = Path("results/")
    snapshot_interval: int = 500
    dump_final_state: bool = True


@dataclass
class SimulationConfig:
    """Top-level simulation configuration parsed from YAML."""

    max_steps: int = 1_000_000
    max_time: float = 365.0
    max_cells: int = 50_000
    seed: int | None = None
    plugins: list[PluginConfig] = field(default_factory=list)
    mutation_store: MutationStoreConfig = field(default_factory=MutationStoreConfig)
    mutation_generator: MutationGeneratorConfig = field(
        default_factory=MutationGeneratorConfig
    )
    rate_function: RateFunctionConfig = field(default_factory=RateFunctionConfig)
    recorder: RecorderConfig = field(default_factory=RecorderConfig)
    export_path : Path | None = None

    def plugins_by_name(self) -> dict[str, PluginConfig]:
        """Return a dict mapping plugin name -> PluginConfig."""
        return {p.name: p for p in self.plugins}


def load_config(path: str | Path) -> SimulationConfig:
    """
    Parse a YAML configuration file and return a SimulationConfig.

    Unknown keys are silently ignored to allow forward-compatible configs.
    """
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text())

    sim_raw = raw.get("simulation", {})
    cfg = SimulationConfig(
        max_steps=sim_raw.get("max_steps", 1_000_000),
        max_time=sim_raw.get("max_time", 365.0),
        max_cells=sim_raw.get("max_cells", 50_000),
        seed=sim_raw.get("seed", None),
    )

    # Rate function
    rf_raw = raw.get("rate_function", {})
    cfg.rate_function = RateFunctionConfig(
        function_type=rf_raw.get("type", "weighted_sum"),
        baseline_birth_rate=rf_raw.get("baseline_birth_rate", 0.5),
        baseline_death_rate=rf_raw.get("baseline_death_rate", 0.2),
        carrying_capacity=rf_raw.get("carrying_capacity", None),
        params={k: v for k, v in rf_raw.items() if k not in {"type", "baseline_birth_rate", "baseline_death_rate", "carrying_capacity"}},
    )

    # Mutation store
    ms_raw = raw.get("mutation_store", {})
    cfg.mutation_store = MutationStoreConfig(
        source=ms_raw.get("source", ":memory:"),
        params={k: v for k, v in ms_raw.items() if k not in {"source"}},
    )

    # Mutation generator
    mg_raw = raw.get("mutation_generator", {})
    cfg.mutation_generator = MutationGeneratorConfig(
        generator_type=mg_raw.get("type", "uniform"),
        params={k: v for k, v in mg_raw.items() if k not in {"type"}},
    )

    # Recorder
    rec_raw = raw.get("recorder", {})
    cfg.recorder = RecorderConfig(
        output_dir=Path(rec_raw.get("output_dir", "results/")),
        snapshot_interval=rec_raw.get("snapshot_interval", 500),
        dump_final_state=rec_raw.get("dump_final_state", True),
    )

    # Plugins
    plugins_raw = raw.get("plugins", {})
    for name, p_raw in plugins_raw.items():
        known_keys = {"type", "target", "category", "weight", "alpha", "params"}
        cfg.plugins.append(
            PluginConfig(
                name=name,
                plugin_type=p_raw["type"],
                target=p_raw.get("target", "rate_function"),
                category=p_raw.get("category", "proliferative"),
                weight=float(p_raw.get("weight", 1.0)),
                alpha=float(p_raw.get("alpha", 0.0)),
                params=p_raw.get("params", {}),
            )
        )

    return cfg

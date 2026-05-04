"""Run a batch of simulations and return pooled non-wt clone sizes."""

from __future__ import annotations

import sys
from pathlib import Path

from evoseer.core.config import SimulationConfig, load_config
from evoseer.main import build_engine
from evoseer.recording.exporter import SimulationExporter


def run_batch(config_path: Path, n_sims: int, base_seed: int) -> list[float]:
    """
    Run n_sims simulations and return pooled non-wt clone sizes.

    Each simulation uses seed = base_seed + i. Clone sizes from all runs
    are concatenated into one flat list (excluding the founding wt clone).
    """
    pooled: list[float] = []

    for i in range(n_sims):
        config = load_config(config_path)
        config.seed = base_seed + i

        engine = build_engine(config)
        founders = [engine.make_founder_cell()]
        result = engine.run(founders)

        exporter = SimulationExporter(result, engine._store, config)
        data = exporter.export()

        for node in data["clone_tree"]["nodes"]:
            if node["id"] != "wt" and node["final_size"] > 0:
                pooled.append(float(node["final_size"]))

        print(
            f"  run {i + 1}/{n_sims} done — {len(data['clone_tree']['nodes']) - 1} clones",
            file=sys.stderr,
        )

    return pooled

"""Prior sampler — draws (weight, alpha) per plugin."""

from __future__ import annotations

import numpy as np


class PriorSampler:
    """
    Samples plugin parameters from independent uniform priors.

    priors format:
        {plugin_name: {weight: [uniform, lo, hi], alpha: [uniform, lo, hi]}}
    """

    def __init__(self, priors: dict) -> None:
        self._priors = priors

    def sample(self, rng: np.random.Generator) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for plugin_name, param_specs in self._priors.items():
            result[plugin_name] = {}
            for param_name, spec in param_specs.items():
                dist, lo, hi = spec[0], float(spec[1]), float(spec[2])
                if dist == "uniform":
                    result[plugin_name][param_name] = float(rng.uniform(lo, hi))
                else:
                    raise ValueError(f"Unknown prior distribution: {dist!r}")
        return result

"""Prior sampler — draws parameters per plugin from independent priors."""

from __future__ import annotations

import numpy as np


class PriorSampler:
    """
    Samples plugin parameters from independent priors.

    priors format (arbitrarily nested):
        {plugin_name: {param: [uniform, lo, hi], group: {param: [uniform, lo, hi]}}}

    A list value is treated as a prior spec; a dict value is recursed into.
    """

    def __init__(self, priors: dict) -> None:
        self._priors = priors

    def sample(self, rng: np.random.Generator) -> dict:
        return self._sample_group(self._priors, rng)

    def _sample_group(self, group: dict, rng: np.random.Generator) -> dict:
        result = {}
        for key, value in group.items():
            if isinstance(value, dict):
                result[key] = self._sample_group(value, rng)
            else:
                dist, lo, hi = value[0], float(value[1]), float(value[2])
                if dist == "uniform":
                    result[key] = float(rng.uniform(lo, hi))
                else:
                    raise ValueError(f"Unknown prior distribution: {dist!r}")
        return result

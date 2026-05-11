"""WeightedSumRate — implements eq. 2.3 / 2.4 from the design doc."""

from __future__ import annotations

import logging

from evoseer.core.config import PluginConfig, RateFunctionConfig
from evoseer.rate_functions.base import RateFunction

logger = logging.getLogger(__name__)


class WeightedSumRate(RateFunction):
    name: str = "weighted_sum"
    """
    Compute per-cell birth and death rates as weighted sums of plugin scores.

    Equations (design doc §5.2):

        b_i = baseline_birth + Σ_{f ∈ proliferative}  w_f · S_f,i · N^α_f
        d_i = baseline_death + Σ_{f ∈ deleterious}    w_f · S_f,i · N^α_f

    Plugins with ``category='proliferative'`` contribute to the birth rate;
    plugins with ``category='deleterious'`` contribute to the death rate.
    A proliferative plugin with a negative weight reduces the birth rate
    (e.g. OIS senescence penalty).

    Rates are clamped to [0, ∞) so they are always valid Gillespie propensities.
    """

    def __init__(self, config: RateFunctionConfig) -> None:
        self._baseline_birth = config.baseline_birth_rate
        self._baseline_death = config.baseline_death_rate

        if config.carrying_capacity is not None:
            if config.carrying_capacity <= 0:
                raise ValueError(
                    f"carrying_capacity must be > 0, got {config.carrying_capacity}. "
                    "Use carrying_capacity: null (or omit) for unlimited growth."
                )
            self._density_coeff = (self._baseline_birth - self._baseline_death) / config.carrying_capacity
        else:
            self._density_coeff = 0.0

    def compute_rates(
        self,
        scores: dict[str, float],
        plugin_configs: dict[str, PluginConfig],
        N: int,
        senescent: bool = False,
    ) -> tuple[float, float]:
        """
        Return (birth_rate, death_rate) for a single cell.

        If ``senescent`` is True, birth is hard-clamped to 0 regardless of
        plugin scores — senescence is irreversible and overrides all other signals.

        Only plugins whose name appears in both ``scores`` and
        ``plugin_configs`` are included; extra keys in either dict are
        silently ignored, which allows callers to pass the full plugin_configs
        dict without pre-filtering.
        """
        if senescent:
            return 0,0 

        birth = self._baseline_birth
        death = self._baseline_death

        for name, score in scores.items():
            pc = plugin_configs.get(name)
            if pc is None:
                continue
            contribution = pc.weight * score * (N ** pc.alpha)
            if pc.category == "proliferative":
                birth += contribution
            elif pc.category == "deleterious":
                death += contribution

        death += self._density_coeff * N

        return max(0.0, birth), max(0.0, death)

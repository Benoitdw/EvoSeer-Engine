"""RateFunction ABC — maps plugin scores to (birth_rate, death_rate)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from evoseer.core.config import PluginConfig, RateFunctionConfig


class RateFunction(ABC):
    """
    Abstract base class for rate functions.

    A RateFunction takes the current per-plugin scores for a single cell and
    returns a (birth_rate, death_rate) pair. The engine sums these across all
    living cells to get the total event rate Λ used by the Gillespie algorithm.

    The RateFunction is intentionally biology-agnostic: it only sees numeric
    scores and configuration metadata (weight, category, alpha).
    """

    def __init__(self, config: RateFunctionConfig) -> None:
        self._config = config

    @abstractmethod
    def compute_rates(
        self,
        scores: dict[str, float],
        plugin_configs: dict[str, PluginConfig],
        N: int,
    ) -> tuple[float, float]:
        """
        Compute (birth_rate, death_rate) for a single cell.

        Args:
            scores:         Mapping of plugin_name -> score for all
                            rate_function-targeted plugins.
            plugin_configs: Mapping of plugin_name -> PluginConfig (provides
                            weight, category, alpha).
            N:              Current population size (used for density
                            dependence via N^alpha).

        Returns:
            (birth_rate, death_rate) — both non-negative floats.
        """
        ...

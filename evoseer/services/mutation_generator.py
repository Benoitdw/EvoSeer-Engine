"""MutationGenerator ABC and built-in implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from evoseer.services.mutation_store import MutationStore


class MutationGenerator(ABC):
    """
    Abstract base class for mutation samplers.

    Each implementation owns the full count-and-sample pipeline for one
    division event: deciding how many mutations to draw (count distribution)
    and which IDs to return (ID distribution).  The engine never touches
    either distribution — it only calls generate(mu_i).

    Class-level attribute:
        name  -- unique string identifier, must match the YAML "type:" key.

    See docs/mutation-pipeline.md for the full design rationale.
    """

    name: str

    @abstractmethod
    def __init__(self, store: MutationStore, params: dict[str, Any]) -> None:
        """
        Pre-compute the sampling distribution over all mutations in the store.

        Called once at simulation startup.  Implementations should loop over
        store.all_ids(), fetch any needed annotations, and cache a normalised
        probability vector for use in generate().
        """
        ...

    @abstractmethod
    def generate(self, mu: float) -> list[int]:
        """
        Return mutation IDs to assign to a daughter cell after one division.

        Args:
            mu: per-division mutation rate for this cell, as returned by the
                mutation_rate plugin.  Generators that use a fixed count may
                ignore this value.

        Returns:
            A (possibly empty) list of mutation IDs sampled from the store.
        """
        ...


class UniformMutationGenerator(MutationGenerator):
    """
    Baseline generator: Poisson count, uniform ID sampling.

    Count is drawn from Poisson(mu).  IDs are sampled uniformly with
    replacement over all mutations in the store.

    YAML config::

        mutation_generator:
          type: uniform
          params:
            seed: 42
    """

    name: str = "uniform"

    def __init__(self, store: MutationStore, params: dict[str, Any]) -> None:
        self._rng = np.random.default_rng(params.get("seed", None))
        all_ids = store.all_ids()
        self._ids: np.ndarray = np.array(all_ids, dtype=np.int64)

    def generate(self, mu: float) -> list[int]:
        """Draw Poisson(mu) mutation IDs uniformly at random (with replacement)."""
        if mu <= 0.0 or len(self._ids) == 0:
            return []
        n = int(self._rng.poisson(mu))
        if n == 0:
            return []
        return self._rng.choice(self._ids, size=n, replace=True).tolist()


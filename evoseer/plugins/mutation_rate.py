"""ConstantMutationRatePlugin — fixed per-division mutation rate."""

from __future__ import annotations

from typing import Any

from evoseer.core.cell import CellState
from evoseer.core.context import SimContext
from evoseer.plugins.base import FeaturePlugin
from evoseer.services.mutation_store import MutationStore


class ConstantMutationRatePlugin(FeaturePlugin):
    """
    Returns a fixed per-division mutation rate μ regardless of cell state.

    YAML config::

        mutation_rate:
          type: constant_mutation_rate
          target: mutation_rate
          params:
            mu: 0.5
    """

    name: str = "constant_mutation_rate"
    involved_pathways: list[str] = []

    def __init__(self, params: dict[str, Any], store: MutationStore) -> None:
        super().__init__(params, store)
        self._mu: float = float(self.get_param("mu", default=0.5))

    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        return self._mu

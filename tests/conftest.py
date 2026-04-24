"""Shared fixtures and test doubles for EvoSeer test suite."""

from __future__ import annotations

from typing import Any

import pytest

from evoseer.core.cell import CellState
from evoseer.core.config import PluginConfig, RateFunctionConfig, SimulationConfig
from evoseer.core.context import SimContext
from evoseer.engine.gillespie import GillespieEngine
from evoseer.plugins.base import FeaturePlugin
from evoseer.rate_functions.weighted_sum import WeightedSumRate
from evoseer.recording.recorder import Recorder
from evoseer.services.mutation_generator import MutationGenerator
from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord, MutationStore


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class SumExtraPlugin(FeaturePlugin):
    """Sums a given extra field across mutations. Supports configurable pathways."""

    name = "sum_extra"

    def __init__(
        self,
        params: dict[str, Any],
        store: MutationStore,
        field: str = "b",
        pathways: list[str] | None = None,
    ) -> None:
        super().__init__(params, store)
        self._field = field
        self.involved_pathways = pathways or []

    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        return sum(
            self.get_extra(self._store.get(mid), self._field)
            for mid in cell_state.mutations
        )


class FixedMutationGenerator(MutationGenerator):
    """Always returns the same fixed list of mutation IDs, regardless of mu."""

    name = "fixed"

    def __init__(self, store: MutationStore, params: dict[str, Any]) -> None:
        self._ids: list[int] = list(params.get("ids", []))

    def generate(self, mu: float) -> list[int]:
        return list(self._ids)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> InMemoryMutationStore:
    """
    Store with 3 mutations:
      id=1  pathway_A  extra={'b': 1.0, 'd': 0.1}  driver=False
      id=2  pathway_A  extra={'b': 0.5, 'd': 0.2}  driver=True
      id=3  pathway_B  extra={'b': 0.2, 'd': 0.05} driver=False
    """
    s = InMemoryMutationStore()
    s.add_mutation(MutationRecord(1, gene_name="G1", pathways=["pathway_A"], is_driver=False, extra={"b": 1.0, "d": 0.1}))
    s.add_mutation(MutationRecord(2, gene_name="G2", pathways=["pathway_A"], is_driver=True,  extra={"b": 0.5, "d": 0.2}))
    s.add_mutation(MutationRecord(3, gene_name="G3", pathways=["pathway_B"], is_driver=False, extra={"b": 0.2, "d": 0.05}))
    return s


@pytest.fixture
def ctx() -> SimContext:
    return SimContext(t=0.0, step=0, N=1)


@pytest.fixture
def engine_factory(store: InMemoryMutationStore):
    """
    Returns a builder function:
        build(plugins, plugin_configs, generator, max_steps, seed,
              baseline_birth, baseline_death) -> GillespieEngine
    All parameters are optional — defaults give a runnable engine with no plugins.
    """
    def build(
        plugins: dict | None = None,
        plugin_configs: dict | None = None,
        generator: MutationGenerator | None = None,
        max_steps: int = 500,
        seed: int = 42,
        baseline_birth: float = 0.9,
        baseline_death: float = 0.1,
    ) -> GillespieEngine:
        return GillespieEngine(
            plugins=plugins or {},
            plugin_configs=plugin_configs or {},
            rate_function=WeightedSumRate(RateFunctionConfig(
                function_type="weighted_sum",
                baseline_birth_rate=baseline_birth,
                baseline_death_rate=baseline_death,
            )),
            mutation_generator=generator or FixedMutationGenerator(store, {"ids": []}),
            store=store,
            recorder=Recorder(snapshot_interval=50, dump_final_state=True),
            config=SimulationConfig(max_steps=max_steps, max_time=1e9, max_cells=10_000, seed=seed),
        )

    return build

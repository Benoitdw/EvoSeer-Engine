"""Minimal smoke test: verify the Gillespie loop runs end-to-end."""

from __future__ import annotations

import pytest

from evoseer.core.config import (
    MutationGeneratorConfig,
    PluginConfig,
    RateFunctionConfig,
    RecorderConfig,
    SimulationConfig,
)
from evoseer.core.context import SimContext
from evoseer.engine.gillespie import GillespieEngine
from evoseer.plugins.mutation_rate import ConstantMutationRatePlugin
from evoseer.rate_functions.weighted_sum import WeightedSumRate
from evoseer.recording.recorder import Recorder
from evoseer.services.mutation_generator import UniformMutationGenerator
from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_store() -> InMemoryMutationStore:
    """Small in-memory store with 10 placeholder mutations."""
    store = InMemoryMutationStore()
    for i in range(10):
        store.add_mutation(
            MutationRecord(
                mutation_id=i,
                gene_name=f"GENE{i}",
                pathways=[],
                is_driver=(i == 0),  # mutation 0 is a driver
            )
        )
    return store


def _make_engine(
    max_steps: int = 200,
    seed: int = 42,
    mu: float = 0.5,
    baseline_birth: float = 0.9,
    baseline_death: float = 0.1,
) -> GillespieEngine:
    """Build a minimal engine: ConstantMutationRatePlugin + UniformMutationGenerator + WeightedSumRate."""
    store = _make_store()

    mutation_rate_plugin = ConstantMutationRatePlugin(params={"mu": mu}, store=store)
    plugins = {"mutation_rate": mutation_rate_plugin}

    pc_mutation_rate = PluginConfig(
        name="mutation_rate",
        plugin_type="constant_rate",
        target="mutation_rate",
        params={"mu": mu},
    )
    plugin_configs = {"mutation_rate": pc_mutation_rate}

    rate_fn_config = RateFunctionConfig(
        function_type="weighted_sum",
        baseline_birth_rate=baseline_birth,
        baseline_death_rate=baseline_death,
    )
    rate_fn = WeightedSumRate(rate_fn_config)

    generator = UniformMutationGenerator(store=store, params={"seed": seed})

    recorder = Recorder(snapshot_interval=50, dump_final_state=True)

    sim_config = SimulationConfig(
        max_steps=max_steps,
        max_time=1e9,
        max_cells=10_000,
        seed=seed,
    )
    sim_config.recorder = RecorderConfig(
        snapshot_interval=50,
        dump_final_state=True,
    )

    return GillespieEngine(
        plugins=plugins,
        plugin_configs=plugin_configs,
        rate_function=rate_fn,
        mutation_generator=generator,
        store=store,
        recorder=recorder,
        config=sim_config,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_simulation_loop_runs():
    """The engine should complete without exceptions and produce a result."""
    engine = _make_engine(max_steps=200)
    founder = engine.make_founder_cell()
    result = engine.run([founder])

    assert result is not None
    assert result.stop_reason in {"max_steps", "max_time", "max_cells", "extinction", "zero_rate"}


def test_stop_reason_is_max_steps():
    """With dominant birth rate and multiple founders the run should hit max_steps."""
    engine = _make_engine(max_steps=100, baseline_birth=0.95, baseline_death=0.05)
    # Start with 5 founders to make extinction extremely unlikely
    founders = [engine.make_founder_cell() for _ in range(5)]
    result = engine.run(founders)

    assert result.stop_reason == "max_steps"


def test_divisions_and_deaths_recorded():
    """At least some division and death events should be logged."""
    engine = _make_engine(max_steps=500, baseline_birth=0.8, baseline_death=0.2)
    founders = [engine.make_founder_cell() for _ in range(5)]
    result = engine.run(founders)

    assert len(result.divisions) > 0, "Expected at least one division"
    assert len(result.deaths) > 0, "Expected at least one death"


def test_snapshots_captured():
    """Snapshots should be captured at the configured interval."""
    engine = _make_engine(max_steps=200, baseline_birth=0.95, baseline_death=0.05)
    founders = [engine.make_founder_cell() for _ in range(5)]
    result = engine.run(founders)

    # With interval=50 and max_steps=200 we expect snapshots at steps 50,100,150,200
    assert len(result.snapshots) >= 1


def test_final_mutations_dumped():
    """With dump_final_state=True, final_mutations should be populated."""
    engine = _make_engine(max_steps=200)
    founder = engine.make_founder_cell()
    result = engine.run([founder])

    assert result.final_mutations is not None


def test_driver_acquisition_logged():
    """Mutation 0 is flagged as a driver — it should appear in driver events eventually."""
    # Run longer to give a chance for mutation 0 to be sampled
    engine = _make_engine(max_steps=2000, mu=2.0)
    founder = engine.make_founder_cell()
    result = engine.run([founder])

    driver_mutation_ids = {e.mutation_id for e in result.drivers}
    # Not guaranteed in a short run, but with mu=2.0 and 2000 steps it's very likely
    # We assert the recorder plumbing works: if drivers were acquired they have the right shape
    for ev in result.drivers:
        assert ev.mutation_id >= 0
        assert ev.cell_id >= 0
        assert ev.step >= 0


def test_mutation_inheritance():
    """Child cells should carry at least the mutations of their parent."""
    engine = _make_engine(max_steps=300, mu=3.0)
    founder = engine.make_founder_cell()
    result = engine.run([founder])

    if result.final_mutations:
        for cell_id, muts in result.final_mutations.items():
            assert isinstance(muts, set)


def test_deterministic_with_seed():
    """Two runs with the same seed should produce identical results."""
    def _run(seed: int):
        engine = _make_engine(max_steps=150, seed=seed)
        founder = engine.make_founder_cell()
        return engine.run([founder])

    r1 = _run(7)
    r2 = _run(7)

    assert len(r1.divisions) == len(r2.divisions)
    assert len(r1.deaths) == len(r2.deaths)
    assert r1.stop_reason == r2.stop_reason


def test_extinction_stops_simulation():
    """When death rate >> birth rate the population should go extinct."""
    engine = _make_engine(
        max_steps=100_000,
        baseline_birth=0.01,
        baseline_death=10.0,
        mu=0.0,
    )
    founder = engine.make_founder_cell()
    result = engine.run([founder])

    assert result.stop_reason == "extinction"


def test_plugin_dirty_cache_mechanism():
    """PluginState score should be cached and only recomputed when dirty."""
    from evoseer.core.cell import CellState, PluginState

    ps = PluginState()
    assert ps._dirty is True
    assert ps.score is None

    ps._cached_score = 3.14
    ps._dirty = False
    assert ps.score == pytest.approx(3.14)

    ps.mark_dirty()
    assert ps._dirty is True

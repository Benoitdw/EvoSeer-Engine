"""Run a batch of simulations and return pooled non-wt clone sizes."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from evoseer.core.config import load_config
from evoseer.engine.gillespie import GillespieEngine
from evoseer.plugins import REGISTRY as _PLUGIN_REGISTRY
from evoseer.rate_functions import REGISTRY as _RATE_FUNCTION_REGISTRY
from evoseer.recording.exporter import SimulationExporter
from evoseer.recording.recorder import Recorder
from evoseer.services import REGISTRY as _GENERATOR_REGISTRY
from evoseer.services.mutation_store import MutationStore

from calibration.stores import BRAF_GOF_ID, NRAS_GOF_ID, build_erk_ois_store

N_FOUNDERS = 500


def _build_engine(config, store: MutationStore) -> GillespieEngine:
    """Build a GillespieEngine from config, injecting a pre-built store."""
    gen_cls = _GENERATOR_REGISTRY[config.mutation_generator.generator_type]
    generator = gen_cls(store, config.mutation_generator.params)

    rf_cls = _RATE_FUNCTION_REGISTRY[config.rate_function.function_type]
    rate_fn = rf_cls(config.rate_function)

    plugins = {}
    for pc in config.plugins:
        cls = _PLUGIN_REGISTRY[pc.plugin_type]
        plugins[pc.name] = cls(pc.params, store)
        plugins[pc.name].name = pc.name

    recorder = Recorder(
        snapshot_interval=config.recorder.snapshot_interval,
        dump_final_state=config.recorder.dump_final_state,
    )

    return GillespieEngine(
        plugins=plugins,
        plugin_configs=config.plugins_by_name(),
        rate_function=rate_fn,
        mutation_generator=generator,
        store=store,
        recorder=recorder,
        config=config,
    )


def _make_founders(engine: GillespieEngine) -> list:
    """10 founders — founders[0] carries BRAF GOF, founders[1] carries NRAS GOF."""
    founders = [engine.make_founder_cell() for _ in range(N_FOUNDERS)]
    founders[0].state.mutations.add(BRAF_GOF_ID)
    founders[1].state.mutations.add(NRAS_GOF_ID)
    engine._recorder.record_driver(step=0, cell_id=founders[0].id, mutation_id=BRAF_GOF_ID)
    engine._recorder.record_driver(step=0, cell_id=founders[1].id, mutation_id=NRAS_GOF_ID)
    return founders


def run_single(config_path: Path, seed: int) -> list[float]:
    """Run one simulation and return non-wt clone sizes."""
    logger.debug("run_single seed=%d config=%s", seed, config_path)
    config = load_config(config_path)
    config.seed = seed

    store = build_erk_ois_store()
    engine = _build_engine(config, store)
    founders = _make_founders(engine)
    result = engine.run(founders)

    exporter = SimulationExporter(result, store, config)

    data = exporter.export()

    if config.recorder.output_dir :
        config.recorder.output_dir.mkdir(exist_ok=True, parents=True)
        export_file = config.recorder.output_dir/ f"simulation.{seed}.evoseer.json"
        logger.debug(f"Simulation {seed} exported to {export_file}")
        exporter.save(export_file)

    clones = [
        float(node["final_size"])
        for node in data["clone_tree"]["nodes"]
        if node["id"] != "wt" and node["final_size"] > 0
    ]
    logger.debug(f"  → {len(clones)} clones")
    return clones


def run_batch(config_path: Path, n_sims: int, base_seed: int) -> list[float]:
    """Run n_sims simulations and return pooled non-wt clone sizes."""
    logger.info(f"run_batch n={n_sims} base_seed={base_seed}")
    pooled: list[float] = []
    for i in range(n_sims):
        pooled.extend(run_single(config_path, seed=base_seed + i))
        logger.debug("  run %d/%d — pooled=%d", i + 1, n_sims, len(pooled))
    return pooled

"""Entry point — build engine from YAML config and run simulation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evoseer.core.config import SimulationConfig, load_config
from evoseer.core.context import SimContext
from evoseer.engine.gillespie import GillespieEngine
from evoseer.plugins import REGISTRY as _PLUGIN_REGISTRY
from evoseer.rate_functions import REGISTRY as _RATE_FUNCTION_REGISTRY
from evoseer.recording.recorder import Recorder
from evoseer.services import REGISTRY as _GENERATOR_REGISTRY
from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord


def build_engine(config: SimulationConfig) -> GillespieEngine:
    """Instantiate all components from a SimulationConfig and return the engine."""
    # Store
    store = InMemoryMutationStore()

    # Mutation generator
    gen_cls = _GENERATOR_REGISTRY.get(config.mutation_generator.generator_type)
    if gen_cls is None:
        raise ValueError(
            f"Unknown mutation generator: {config.mutation_generator.generator_type}"
        )
    generator = gen_cls(store, config.mutation_generator.params)

    # Rate function
    rf_cls = _RATE_FUNCTION_REGISTRY.get(config.rate_function.function_type)
    if rf_cls is None:
        raise ValueError(f"Unknown rate function: {config.rate_function.function_type}")
    rate_fn = rf_cls(config.rate_function)

    # Plugins
    plugins = {}
    plugin_configs = config.plugins_by_name()
    for pc in config.plugins:
        plugin_cls = _PLUGIN_REGISTRY.get(pc.plugin_type)
        if plugin_cls is None:
            raise ValueError(f"Unknown plugin type: {pc.plugin_type}")
        plugins[pc.name] = plugin_cls(pc.params, store)
        plugins[pc.name].name = pc.name

    # Recorder
    recorder = Recorder(
        snapshot_interval=config.recorder.snapshot_interval,
        dump_final_state=config.recorder.dump_final_state,
    )

    return GillespieEngine(
        plugins=plugins,
        plugin_configs=plugin_configs,
        rate_function=rate_fn,
        mutation_generator=generator,
        store=store,
        recorder=recorder,
        config=config,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run an EvoSeer simulation")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "default.yaml"),
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--n-founders",
        type=int,
        default=1,
        help="Number of founder cells",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    engine = build_engine(config)

    founders = [engine.make_founder_cell() for _ in range(args.n_founders)]
    result = engine.run(founders)

    print(f"Simulation finished: {result.stop_reason}")
    print(f"  divisions : {len(result.divisions)}")
    print(f"  deaths    : {len(result.deaths)}")
    print(f"  drivers   : {len(result.drivers)}")
    print(f"  snapshots : {len(result.snapshots)}")
    if result.final_mutations is not None:
        surviving = len(result.final_mutations)
        print(f"  surviving cells: {surviving}")


if __name__ == "__main__":
    main()

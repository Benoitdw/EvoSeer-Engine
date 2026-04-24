# EvoSeer Engine

A biologically-informed stochastic evolutionary simulator. EvoSeer models a population of cells evolving through time via the Gillespie algorithm, where each cell carries mutations that affect its biological parameters (proliferation, senescence, immunogenicity, mutation rate, etc.).

## Design

The engine is built around three principles:

- **Plugin architecture** — biological features are self-contained modules that can be added, removed, or swapped without touching the simulation engine
- **Separation of concerns** — simulation engine, rate computation, mutation generation, and recording are independent components
- **Configuration-driven** — a YAML file controls which plugins are active, their parameters, and how they connect

```
┌─────────────────────────────────────────────────┐
│  Layer 1 — Data / State                         │
│  Cell, CellState, PluginState                   │
├─────────────────────────────────────────────────┤
│  Layer 2 — Feature Plugins                      │
│  FeaturePlugin ABC + concrete implementations   │
├─────────────────────────────────────────────────┤
│  Layer 3 — Rate Function                        │
│  RateFunction ABC + WeightedSumRate             │
├─────────────────────────────────────────────────┤
│  Layer 4 — Simulation Engine                    │
│  GillespieEngine (biology-agnostic)             │
├─────────────────────────────────────────────────┤
│  Layer 5 — Recorder                             │
│  Event logging, snapshots, driver tracking      │
├─────────────────────────────────────────────────┤
│  Services: MutationStore, MutationGenerator     │
│  Config: YAML                                   │
└─────────────────────────────────────────────────┘
```

## Project structure

```
evoseer/
├── core/
│   ├── cell.py               # Cell, CellState, PluginState
│   ├── context.py            # SimContext
│   └── config.py             # YAML parsing, SimulationConfig, PluginConfig
├── plugins/
│   ├── base.py               # FeaturePlugin ABC
│   └── mutation_rate.py      # ConstantMutationRatePlugin
├── rate_functions/
│   ├── base.py               # RateFunction ABC
│   └── weighted_sum.py       # WeightedSumRate
├── services/
│   ├── mutation_store.py     # MutationStore + InMemoryMutationStore
│   └── mutation_generator.py # ABC + UniformMutationGenerator
├── engine/
│   ├── gillespie.py          # GillespieEngine
│   └── events.py             # Event types
├── recording/
│   └── recorder.py           # Recorder
└── config/
    └── default.yaml          # Default configuration
```

## Getting started

Requires Python 3.11+. Dependencies are managed with [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run pytest
```

## Configuration

Simulations are configured via YAML. See `evoseer/config/default.yaml` for the full default:

```yaml
simulation:
  max_steps: 1_000_000
  max_time: 365.0
  max_cells: 50_000
  seed: 42
  snapshot_interval: 500
  dump_final_state: true

mutation_generator:
  type: uniform

rate_function:
  type: weighted_sum
  baseline_birth_rate: 0.5
  baseline_death_rate: 0.2

plugins:
  mutation_rate:
    type: constant_rate
    target: mutation_rate
    params:
      mu: 0.5
```

### Stopping conditions

The engine stops on the first condition met:

| Condition | Config key |
|-----------|------------|
| Step limit | `max_steps` |
| Time limit | `max_time` |
| Population ceiling | `max_cells` |
| Extinction | *(automatic)* |

## Plugins

Each plugin implements the `FeaturePlugin` ABC:

- `init_state(cell_state, ctx)` — create initial plugin state for a new cell
- `compute_score(cell_state, ctx)` — compute the feature score (called only when the plugin state is dirty)
- `on_division(parent_state, ctx)` — handle cell division, returns `(parent_plugin_state, child_plugin_state)`

Plugin states carry a `_dirty` flag. The score is recomputed only when mutations arrive in a relevant pathway — all other accesses use the cached value.

### Implemented (Phase 1)

| Plugin | Type key | Description |
|--------|----------|-------------|
| `ConstantMutationRatePlugin` | `constant_rate` | Fixed per-division mutation rate μ |

### Planned (Phase 2)

- `PathwayActivationPlugin` — sigmoid-weighted GOF/LOF mutations for MAPK, PI3K, Apoptosis
- `OISPlugin` — oncogene-induced senescence hazard with division counter
- `ImmunogenicityPlugin` — neoantigen scoring with immune escape modulation

## Recorder output

The recorder captures:

- **Division events** — `(step, parent_id, child_id)`
- **Death events** — `(step, cell_id)`
- **Driver acquisitions** — `(step, cell_id, mutation_id)`
- **Periodic snapshots** — population size and time at configurable interval (default every 500 steps)
- **Final state** — mutational profile of all living cells (if `dump_final_state: true`)

The phylogenetic tree is fully reconstructable from the division/death event log — it is not stored in memory during the simulation.

## Roadmap

### Phase 1 — Pure Python ✓

Architecture validated end-to-end. 10 tests passing covering the full Gillespie loop, event recording, determinism, extinction, and plugin caching.

### Phase 2 — Rust core + Python plugins via PyO3

Goal: 10–100× speedup on the simulation hot path while keeping plugin development easy.

The Rust crate (`evoseer-core`) will implement the engine and performance-critical plugins. Python plugins from Phase 1 will work unchanged via a `PyPluginBridge`. The `_dirty` cache amortizes the GIL acquisition overhead — Python plugins are only called when a mutation arrives in a relevant pathway.

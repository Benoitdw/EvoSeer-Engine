# EvoSeer Framework — Architecture Design

## 1. Overview

EvoSeer is a biologically-informed stochastic evolutionary simulator. It models a population of cells evolving through time via a Gillespie algorithm, where each cell carries mutations that impact its biological parameters (proliferation, senescence, immunogenicity, mutation rate, etc.).

The framework is designed around **modularity**: biological features are implemented as plugins that can be added, removed, or swapped without modifying the simulation engine. The simulation engine is agnostic to the biology — it only knows about cells, scores, and rates.

### Design principles

- **Plugin architecture** for biological features — each feature is a self-contained module
- **Separation of concerns** — simulation engine, rate computation, mutation generation, and recording are independent components
- **Configuration-driven** — a YAML file defines which plugins to activate, their parameters, and how they connect
- **Training-agnostic** — the recorder captures enough data for ABC, ML, or any future training method


## 2. Architecture layers

```
┌─────────────────────────────────────────────────┐
│  Layer 1 — Data / State                         │
│  Cell, CellState, PluginState                   │
├─────────────────────────────────────────────────┤
│  Layer 2 — Feature Plugins                      │
│  FeaturePlugin ABC + concrete implementations   │
├─────────────────────────────────────────────────┤
│  Layer 3 — Rate Function (plugin)               │
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


## 3. Layer 1 — Data / State

### 3.1 Cell

The `Cell` represents an entity in the simulation with identity and lineage.

```python
class Cell:
    id: int                     # unique, assigned by the engine
    parent_id: int | None       # id of the parent cell (None for founder)
    children_ids: list[int]     # ids of living children (purged on child death)
    birth_step: int             # Gillespie step at which this cell was created
    alive: bool
    state: CellState
```

**Memory management**: when a cell dies, it is removed from the active pool. Its `id` is retained in the parent's `children_ids` list only if the parent is still alive — dead children are purged from the list. The Recorder has already logged all lineage events, so the phylogenetic tree is reconstructable from logs.

### 3.2 CellState

The biological state of a cell. Decoupled from identity/lineage.

```python
@dataclass
class CellState:
    mutations: set[int]                         # mutation_ids from MutationStore
    plugin_states: dict[str, PluginState]       # keyed by plugin name
```

### 3.3 PluginState

Base dataclass for per-cell plugin state. Each plugin subclasses this to add its own fields.

```python
@dataclass
class PluginState:
    _cached_score: float | None = None
    _dirty: bool = True

    @property
    def score(self) -> float:
        """Getter — returns cached score or triggers recomputation."""
        # Recomputation is handled by the engine calling compute_score
        # when _dirty is True, then caching the result here.
        return self._cached_score

    def mark_dirty(self) -> None:
        self._dirty = True
```

Example subclass:

```python
@dataclass
class OISState(PluginState):
    t_trigger: int | None = None    # step at which first OIS-triggering mutation was acquired
    k_divisions: int = 0            # number of divisions since trigger
```


## 4. Layer 2 — Feature Plugins

### 4.1 FeaturePlugin ABC

```python
from abc import ABC, abstractmethod

class FeaturePlugin(ABC):
    """Base class for all biological feature plugins."""

    name: str                                   # unique identifier, matches YAML key
    involved_pathways: list[str]                # pathways that trigger score recalculation

    @abstractmethod
    def init_state(self, cell_state: CellState, ctx: SimContext) -> PluginState:
        """Create initial plugin state for a new cell."""
        ...

    @abstractmethod
    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        """Compute the feature score for a cell. Called when PluginState._dirty is True."""
        ...

    @abstractmethod
    def on_division(
        self, parent_state: CellState, ctx: SimContext
    ) -> tuple[PluginState, PluginState]:
        """
        Handle cell division.
        Returns (updated_parent_plugin_state, child_plugin_state).
        """
        ...
```

### 4.2 SimContext

Lightweight context object passed to plugin methods.

```python
@dataclass(frozen=True)
class SimContext:
    t: float        # continuous time
    step: int       # current Gillespie step
    N: int          # current population size
```

### 4.3 Score caching and dirty mechanism

Each `PluginState` carries a `_dirty` flag. The score is recomputed only when dirty.

**When does a plugin state become dirty?**

1. **At division**: `on_division` produces new plugin states — both parent and child start dirty.
2. **On new mutation acquisition**: the engine checks which pathways the mutated gene belongs to (via `MutationStore`), then marks dirty only the plugins whose `involved_pathways` intersect with those pathways.

The engine flow for score access:

```python
def get_score(cell: Cell, plugin: FeaturePlugin, ctx: SimContext) -> float:
    ps = cell.state.plugin_states[plugin.name]
    if ps._dirty:
        ps._cached_score = plugin.compute_score(cell.state, ctx)
        ps._dirty = False
    return ps._cached_score
```

### 4.4 Concrete plugins (v1)

**PathwayActivationPlugin** (type: `pathway_activation`)
- Used for MAPK, PI3K, Apoptotic pathways
- `compute_score`: sigmoid of weighted GOF/LOF mutations in the pathway (eq. 2.8)
- `on_division`: copy parent state (no internal state beyond mutations)
- `involved_pathways`: e.g. `["MAPK"]`

**OISPlugin** (type: `ois`)
- `compute_score`: OIS hazard λ_OIS = S_i · λ_0 · Hill(u_i, K, n) (eq. 2.10)
- `on_division`: increment `k_divisions`, copy `t_trigger`
- `involved_pathways`: `["OIS_act", "OIS_inh"]`
- Internal state: `OISState(t_trigger, k_divisions)`

**ConstantMutationRatePlugin** (type: `constant_rate`)
- `compute_score`: returns hardcoded `μ` from params
- `on_division`: copy (no internal state)
- `involved_pathways`: `[]` (never dirty from mutations)
- Placeholder for future DNA repair pathway plugin (eq. 2.1)

**ImmunogenicityPlugin** (type: `immunogenicity`) — v2
- `compute_score`: Φ from eq. 2.7 (sum of neoantigen scores × immunosuppression)
- `on_division`: copy
- `involved_pathways`: `["immune_escape"]`


## 5. Layer 3 — Rate Function

### 5.1 RateFunction ABC

```python
class RateFunction(ABC):
    @abstractmethod
    def compute_rates(
        self,
        scores: dict[str, float],
        plugin_configs: dict[str, PluginConfig],
        N: int,
    ) -> tuple[float, float]:
        """
        Compute (birth_rate, death_rate) from plugin scores.

        plugin_configs provides weight, category, alpha for each plugin
        whose target is 'rate_function'.
        """
        ...
```

### 5.2 WeightedSumRate

Implements eq. 2.3 / 2.4:

```
b_i = Σ_{f ∈ proliferative} w_f · S_f,i · N^α_f
d_i = Σ_{f ∈ deleterious}   w_f · S_f,i · N^α_f
```

Proliferative plugins with negative weights effectively reduce birth rate (e.g. OIS).


## 6. Services

### 6.1 MutationStore

In-memory lookup for mutation annotations. Source-agnostic (DB, CSV, dict).

```python
class MutationStore:
    def get(self, mutation_id: int) -> MutationRecord:
        """Get all annotations for a mutation."""
        ...

    def get_gene_pathways(self, mutation_id: int) -> list[str]:
        """Get pathways associated with the gene this mutation affects."""
        ...

    def is_driver(self, mutation_id: int) -> bool | None:
        """Check if mutation is flagged as driver. None if unknown."""
        ...
```

`MutationRecord` aggregates all annotation data (boostdm, genebe, vip, neoantigen, gene info, pathways).

**Database enrichment required**: the current schema needs a `pathways` table and a `gene_pathway` join table to support the `get_gene_pathways` lookup.

```sql
CREATE TABLE pathways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pathway_name TEXT NOT NULL UNIQUE,   -- e.g. 'MAPK', 'OIS_act', 'NER'
    pathway_type TEXT                     -- e.g. 'signaling', 'repair', 'senescence'
);

CREATE TABLE gene_pathway (
    gene_id INTEGER NOT NULL,
    pathway_id INTEGER NOT NULL,
    role TEXT,                            -- 'activator', 'inhibitor'
    FOREIGN KEY (gene_id) REFERENCES genes(id),
    FOREIGN KEY (pathway_id) REFERENCES pathways(id),
    UNIQUE(gene_id, pathway_id)
);
```

### 6.2 MutationGenerator

Assigns occurrence probabilities to mutations and samples from them.

```python
class MutationGenerator(ABC):
    @abstractmethod
    def __init__(self, store: MutationStore, params: dict):
        """Compute probability distribution over all mutations in the store."""
        ...

    @abstractmethod
    def sample(self, n: int) -> list[int]:
        """Sample n mutation_ids from the distribution."""
        ...
```

**CosmicMutationGenerator**: uses COSMIC SBS signatures weighted by tissue prevalence to compute per-mutation probabilities from their trinucleotide context. Static distribution computed at init.

**UniformMutationGenerator**: equal probability for all mutations. Baseline/testing.


## 7. Layer 4 — Simulation Engine

### 7.1 GillespieEngine

The engine is biology-agnostic. It orchestrates the Gillespie algorithm.

```python
class GillespieEngine:
    def __init__(
        self,
        plugins: dict[str, FeaturePlugin],
        rate_function: RateFunction,
        mutation_generator: MutationGenerator,
        store: MutationStore,
        recorder: Recorder,
        config: SimulationConfig,
    ): ...

    def run(self, initial_cells: list[Cell]) -> SimulationResult:
        """Run the full simulation."""
        ...
```

### 7.2 Step flow

One Gillespie step:

```
1. COLLECT SCORES
   For each living cell, for each plugin with target='rate_function':
       score = plugin_state.score  (getter checks _dirty, recomputes if needed)

2. COMPUTE RATES
   For each cell:
       scores = {plugin_name: score}
       (b_i, d_i) = rate_function.compute_rates(scores, plugin_configs, N)
       λ_i = b_i + d_i

3. COMPUTE TIMING
   Λ = Σ λ_i
   Δt = -ln(U) / Λ
   t += Δt

4. SELECT CELL
   Pick cell i with probability λ_i / Λ

5. SELECT EVENT
   If U < b_i / λ_i → division, else → death

6. EXECUTE EVENT

   DEATH:
       cell.alive = False
       Purge cell.id from parent.children_ids
       recorder.record_death(step, cell.id)

   DIVISION:
       a. Call on_division on all plugins → (parent_ps', child_ps')
       b. Get μ_i from mutation_rate plugin score
       c. n = Poisson(μ_i)
       d. new_mutations = mutation_generator.sample(n)
       e. Create child Cell with inherited mutations + new_mutations
       f. For each new mutation:
            - Get gene pathways from store
            - Mark _dirty on plugins whose involved_pathways intersect
       g. Check if any new mutation is_driver → recorder.record_driver(...)
       h. recorder.record_division(step, parent.id, child.id)

7. SNAPSHOT (every x steps, configurable)
   recorder.snapshot(step, t, n_alive, n_dead_cumulative)
```

### 7.3 Stopping conditions

The engine stops when any of these is met:
- `step >= max_steps`
- `t >= max_time`
- `N >= max_cells`
- `N == 0` (extinction)


## 8. Layer 5 — Recorder

### 8.1 Recorded data

**Per-event (real-time):**
- Division events: `(step, parent_id, child_id)`
- Death events: `(step, cell_id)`
- Driver acquisition: `(step, cell_id, mutation_id)`

**Periodic snapshots (every x steps, default x=500):**
- `step`, `t` (continuous time)
- `n_alive`, `n_dead_cumulative`
- Additional metrics as needed

**End-of-simulation (if configured in YAML):**
- Full mutational state of all living cells: `{cell_id: set[mutation_id]}`
- Terminal classification: `no_tumor | nevus | melanoma`

### 8.2 Phylogenetic tree reconstruction

The tree is reconstructable from division/death event logs:
- Each division log `(step, parent_id, child_id)` is an edge
- Each death log `(step, cell_id)` marks a leaf as dead
- Living cells at simulation end are extant leaves

No need to store the tree structure in memory during simulation — `Cell.parent_id` and `Cell.children_ids` are maintained only for living cells for runtime use.


## 9. Configuration (YAML)

```yaml
simulation:
  max_steps: 1_000_000
  max_time: 365.0
  max_cells: 50_000
  seed: 42
  snapshot_interval: 500        # record snapshot every N steps
  dump_final_state: true        # dump full mutational state at end

mutation_store:
  source: "path/to/mutations.db"

mutation_generator:
  type: "cosmic"
  params:
    tissue: "Skin-Melanoma"

rate_function:
  type: "weighted_sum"

plugins:
  mapk:
    type: "pathway_activation"
    target: "rate_function"
    category: "proliferative"
    weight: 1.0
    alpha: 0.0
    params:
      sigmoid_slope: 1.0

  pi3k:
    type: "pathway_activation"
    target: "rate_function"
    category: "proliferative"
    weight: 1.0
    alpha: 0.0
    params:
      sigmoid_slope: 1.0

  apoptosis:
    type: "pathway_activation"
    target: "rate_function"
    category: "deleterious"
    weight: 1.0
    alpha: 0.0
    params:
      sigmoid_slope: 1.0

  ois:
    type: "ois"
    target: "rate_function"
    category: "proliferative"
    weight: -1.0
    alpha: 0.0
    params:
      K: 12.9
      n: 2
      lambda_0: 1.0

  mutation_rate:
    type: "constant_rate"
    target: "mutation_rate"
    params:
      mu: 0.5

recorder:
  output_dir: "results/"
```


## 10. Implementation roadmap

### Phase 1 — Pure Python (v1)

Goal: validate the architecture and the biology. Get first simulation results.

Everything in Python. Focus on correctness, not performance.

```
evoseer/
├── core/
│   ├── cell.py                 # Cell, CellState, PluginState
│   ├── context.py              # SimContext
│   └── config.py               # YAML parsing, SimulationConfig, PluginConfig
├── plugins/
│   ├── base.py                 # FeaturePlugin ABC
│   ├── pathway_activation.py   # MAPK, PI3K, Apoptosis
│   ├── ois.py                  # OIS plugin
│   ├── mutation_rate.py        # Constant rate (v1), DNA repair (v2)
│   └── immunogenicity.py       # v2
├── rate_functions/
│   ├── base.py                 # RateFunction ABC
│   └── weighted_sum.py         # WeightedSumRate (eq. 2.3/2.4)
├── services/
│   ├── mutation_store.py       # MutationStore
│   └── mutation_generator.py   # ABC + Cosmic + Uniform
├── engine/
│   ├── gillespie.py            # GillespieEngine
│   └── events.py               # Event types
├── recording/
│   └── recorder.py             # Recorder
├── config/
│   └── default.yaml            # Default configuration
└── main.py                     # Entry point
```

### Phase 2 — Rust core + Python plugins via PyO3 (v2)

Goal: 10-100x performance on the simulation hot path while keeping plugin development easy.

The Rust/Python hybrid uses PyO3 to expose the engine as a Python package. Plugins can be written in either language — the engine sees only the trait interface.

**Architecture:**

```
evoseer/
├── crates/
│   └── evoseer-core/           # Rust crate
│       ├── src/
│       │   ├── lib.rs
│       │   ├── cell.rs         # Cell, CellState, PluginState structs
│       │   ├── context.rs      # SimContext
│       │   ├── plugin.rs       # FeaturePlugin trait
│       │   ├── rate_function.rs
│       │   ├── engine.rs       # GillespieEngine
│       │   ├── recorder.rs
│       │   ├── store.rs        # MutationStore
│       │   ├── generator.rs    # MutationGenerator
│       │   └── bridge.rs       # PyPluginBridge (PyO3 ↔ trait)
│       └── Cargo.toml
├── python/
│   └── evoseer/
│       ├── __init__.py         # re-exports from Rust via PyO3
│       ├── plugins/            # Python-native plugins
│       │   ├── base.py         # Python ABC mirroring Rust trait
│       │   ├── immunogenicity.py
│       │   └── ...
│       └── config.py
├── pyproject.toml              # maturin build config
└── config/
    └── default.yaml
```

**How dual-language plugins work:**

```rust
// Rust — the native trait
pub trait FeaturePlugin: Send + Sync {
    fn compute_score(&self, state: &CellState, ctx: &SimContext) -> f64;
    fn on_division(&self, state: &CellState, ctx: &SimContext)
        -> (PluginState, PluginState);
    fn init_state(&self, state: &CellState, ctx: &SimContext) -> PluginState;
    fn involved_pathways(&self) -> &[String];
}

// Rust-native plugin — zero overhead
pub struct OISPlugin { /* ... */ }
impl FeaturePlugin for OISPlugin { /* ... */ }

// Bridge for Python plugins — calls through PyO3
pub struct PyPluginBridge {
    py_object: PyObject,
}
impl FeaturePlugin for PyPluginBridge {
    fn compute_score(&self, state: &CellState, ctx: &SimContext) -> f64 {
        Python::with_gil(|py| {
            self.py_object
                .call_method1(py, "compute_score", (state, ctx))
                .extract(py)
        })
    }
    // ... same pattern for on_division, init_state
}
```

```python
# Python plugin — easy to write, ~1-5μs overhead per call
class ImmunogenicityPlugin:
    involved_pathways = ["immune_escape"]

    def compute_score(self, cell_state, ctx):
        return sum(n.score for n in cell_state.neoantigens) * (1 - self.immunosuppression)

    def on_division(self, parent_state, ctx):
        return self.state.copy(), self.state.copy()

    def init_state(self, cell_state, ctx):
        return ImmunogenicityState()
```

**YAML plugin config:**

```yaml
plugins:
  ois:
    lang: "rust"                # loaded as native Rust impl — zero overhead
    type: "ois"
    target: "rate_function"
    # ...
  immunogenicity:
    lang: "python"              # loaded via PyPluginBridge — small overhead, mitigated by _dirty cache
    type: "evoseer.plugins.immunogenicity.ImmunogenicityPlugin"
    target: "rate_function"
    # ...
```

**Performance characteristics:**
- Rust-native plugins: zero overhead, called directly via trait dispatch
- Python plugins: ~1-5μs per call (GIL acquisition + marshalling), but the `_dirty` cache means calls happen only when the plugin state changes (new mutation in a relevant pathway), not at every Gillespie step
- Engine hot loop (rate calculation, cell selection, timing): pure Rust, no Python calls
- Expected speedup: 10-100x on the engine, with Python plugin overhead amortized by caching

**Migration path from v1 to v2:**
- The `FeaturePlugin` interface is identical in both phases (same methods, same semantics)
- Python plugins from v1 work unchanged in v2 via `PyPluginBridge`
- Performance-critical plugins (OIS, pathway activation) are rewritten in Rust
- Experimental or rapidly-changing plugins stay in Python
- No architectural refactoring needed — it's a mechanical port of the hot path


## 11. Open questions for implementation

1. **OIS arrest mechanics**: when OIS fires, the cell stops dividing. Is this modeled as `alive=True` but birth_rate=0 (senescent cell stays in population), or is it effectively removed from the active pool? Impacts N and carrying capacity.

2. **Proliferative reserve cells** (section 2.b.c.c of the paper): the fraction ρ of cells with suppressed OIS hazard. Is this a plugin concern or an engine concern?

3. **Initial population**: how many founder cells, with what mutations? Configurable in YAML or separate input file?

4. **Two-hit model for tumor suppressors**: LOF requires biallelic inactivation. Is this tracked per-gene in the plugin state, or is it a property of the mutation annotation (the mutation is already annotated as "causes LOF")?

5. **Performance**: for large populations (50k cells), the O(N) score collection at each step may become a bottleneck. Incremental Λ maintenance (updating only changed cells) is a future optimization to keep in mind.

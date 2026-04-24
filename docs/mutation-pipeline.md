# Mutation Pipeline

This document describes how new mutations are assigned to daughter cells at each
division event, and the design rationale behind the separation of responsibilities.

## Overview

Mutation assignment involves two independent concerns:

1. **How many mutations does this cell get?** — determined by the cell's biological
   state (DNA repair capacity, replication stress, etc.)
2. **Which mutations are they?** — determined by the tissue-specific mutational
   process (SBS signatures, uniform baseline, etc.)

These two concerns map to two separate components:

| Component | Responsibility | Configured via |
|-----------|---------------|----------------|
| `mutation_rate` plugin | Computes μ_i, the per-division rate for cell i | `plugins:` block |
| `MutationGenerator` | Given μ_i, draws count + samples mutation IDs | `mutation_generator:` block |

The engine knows neither Poisson nor mutation IDs. Its only interface is:

```python
mu_i = get_score(cell, mutation_rate_plugin)      # float
new_mutations = mutation_generator.generate(mu_i) # list[int]
```

---

## The `mutation_rate` plugin

Any plugin with `target: mutation_rate` acts as the per-cell mutation rate source.
Its `compute_score()` returns a non-negative float μ_i for the current cell.

```yaml
plugins:
  mutation_rate:
    type: constant_rate
    target: mutation_rate
    params:
      mu: 0.5
```

Swapping this plugin (e.g. for a DNA-repair pathway plugin that raises μ_i when NER
genes are lost) requires no changes to the engine or the generator.

---

## The `MutationGenerator`

`MutationGenerator` is an ABC with two mandatory methods:

```python
class MutationGenerator(ABC):
    name: str   # must match the "type:" key in the YAML config

    @abstractmethod
    def __init__(self, store: MutationStore, params: dict) -> None:
        """
        Pre-compute the sampling distribution over all mutations in the store.
        Called once at simulation startup — not per step.
        """
        ...

    @abstractmethod
    def generate(self, mu: float) -> list[int]:
        """
        Given the per-division rate mu, return the list of mutation IDs
        to assign to the daughter cell.
        The generator owns the count distribution and the ID distribution.
        """
        ...
```

### `name` and YAML selection

The `name` class attribute works exactly like `FeaturePlugin.name`: it is the key
that maps the YAML `type:` field to a concrete implementation.

```yaml
mutation_generator:
  type: uniform   # → resolved to the class whose name == "uniform"
  params:
    seed: 42
```

### `__init__` and the probability vector

At startup the generator loops over `store.all_ids()`, queries each mutation's
annotations, and builds a normalised probability vector that is kept in memory.
This is a one-time cost; `generate()` only ever calls `np.random.choice` against
the pre-built vector.

For `UniformMutationGenerator` every mutation gets equal weight. For a future
`CosmicMutationGenerator` the weight comes from the COSMIC SBS signature for the
target tissue, looked up via each mutation's trinucleotide context:

```python
def __init__(self, store, params):
    tissue = params["tissue"]
    ids = store.all_ids()
    weights = np.array([
        self._sbs_weight(store.get(i), tissue) for i in ids
    ])
    weights /= weights.sum()
    self._ids = np.array(ids)
    self._probs = weights      # cached, reused at every generate() call
```

### Why Poisson lives in the generator, not the engine

The Poisson draw (`n ~ Poisson(μ_i)`) is a modelling choice. Keeping it in the
engine would mean any change to the count distribution — fixed count, zero-inflated
model, negative binomial — requires editing the simulation core. Keeping it in
`generate()` means it is a one-class change, fully isolated from the loop.

A generator that ignores `mu` entirely is valid:

```python
class FixedCountGenerator(MutationGenerator):
    name: str = "fixed"

    def __init__(self, store, params):
        self._n = int(params.get("n", 1))
        self._ids = np.array(store.all_ids())
        self._rng = np.random.default_rng(params.get("seed"))

    def generate(self, mu: float) -> list[int]:
        return self._rng.choice(self._ids, size=self._n, replace=True).tolist()
```

Register it in the factory, set `type: fixed` in YAML — no engine changes needed.

---

## Built-in generators

### `uniform`

```yaml
mutation_generator:
  type: uniform
  params:
    seed: 42
```

- Count: `n ~ Poisson(μ)`
- IDs: sampled uniformly with replacement over all mutations in the store
- Use: testing, null model

### `cosmic` *(Phase 2)*

```yaml
mutation_generator:
  type: cosmic
  params:
    tissue: "Skin-Melanoma"
```

- Count: `n ~ Poisson(μ)`
- IDs: sampled proportionally to COSMIC SBS signature weights for the target tissue,
  using each mutation's trinucleotide context stored in `MutationRecord`
- Use: biologically realistic mutational spectra

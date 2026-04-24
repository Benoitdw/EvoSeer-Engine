# Test structure

## Layout

```
tests/
  conftest.py                           # shared fixtures and test doubles
  test_minimal.py                       # end-to-end smoke tests (full engine)
  engine/
    test_cache.py                       # dirty/cache and pathway-recompute mechanism
  plugins/
    test_constant_mutation_rate.py      # one file per plugin
  services/
    test_uniform_mutation_generator.py  # one file per service
    test_mutation_inheritance.py        # child/parent mutation inheritance
  rate_functions/
    test_weighted_sum.py                # one file per rate function
```

## conftest.py — shared fixtures

Available in every test file automatically.

| Fixture | Type | Description |
|---|---|---|
| `store` | `InMemoryMutationStore` | 3 mutations: ids 1 & 2 in `pathway_A`, id 3 in `pathway_B`, each with `extra={"b": ..., "d": ...}` |
| `ctx` | `SimContext` | `t=0, step=0, N=1` |
| `engine_factory` | `callable` | Returns a `GillespieEngine` — see below |

### engine_factory

```python
engine = engine_factory(
    plugins={"my_plugin": plugin},      # default: {}
    plugin_configs={"my_plugin": pc},   # default: {}
    generator=FixedMutationGenerator(...),  # default: no mutations
    max_steps=500,                      # default: 500
    seed=42,                            # default: 42
    baseline_birth=0.9,                 # default: 0.9
    baseline_death=0.1,                 # default: 0.1
)
```

### Test doubles

**`SumExtraPlugin`** — minimal plugin that sums an `extra` field across mutations. Accepts configurable `field` and `pathways`. Use it to test engine mechanics without writing a real plugin.

```python
plugin = SumExtraPlugin(params={}, store=store, field="b", pathways=["pathway_A"])
```

**`FixedMutationGenerator`** — always returns the same list of mutation IDs regardless of `mu`. Use it to make division events deterministic in engine tests.

```python
gen = FixedMutationGenerator(store, {"ids": [1]})  # always produces mutation 1
```

## Adding tests for a new component

- **New plugin** → `tests/plugins/test_<plugin_name>.py`
- **New service** → `tests/services/test_<service_name>.py`
- **New rate function** → `tests/rate_functions/test_<rate_function_name>.py`

All fixtures from `conftest.py` are available. The `store` fixture pre-populates pathway_A and pathway_B — use those pathway names in `SumExtraPlugin` to test the dirty/recompute mechanism.

## Running tests

```bash
uv run pytest          # all tests
uv run pytest tests/plugins/   # one directory
uv run pytest -v       # verbose
```

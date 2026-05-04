# ABC Calibration — Design

## 1. Overview

A rejection-ABC calibration layer that sits entirely above the existing EvoSeer engine.
The engine is never modified. The calibration layer speaks to it only through
`load_config` + `build_engine` + `engine.run()`, exactly as `main.py` does today.

**Goal**: infer the `weight` (w) and `alpha` (α) of each plugin by comparing the
pooled clone-size distribution produced by the simulator to an observed distribution
derived from ISIC 2024 benign lesion data (`tbp_lv_areaMM2`).


## 2. Module structure

```
calibration/
├── __init__.py
├── abc.py          # RejectionABC orchestrator
├── sampler.py      # Prior sampler — draws (alpha, w) per plugin
├── summary.py      # Extracts clone size vector from SimulationResult
├── distance.py     # Pluggable loss functions
├── config_gen.py   # Generates a temp config.yaml from base config + param overrides
├── runner.py       # Runs a batch of X simulations, returns pooled clone sizes
└── target.py       # Loads the observed target distribution from ISIC 2024
```


## 3. Data flow

```
RejectionABC
│
├── 1. load_target()           → flat list[float] of observed clone sizes
├── 2. load base config.yaml
│
└── for each ABC iteration (up to n_samples):
    │
    ├── sampler.sample()
    │     └── draws {plugin_name: {weight: w, alpha: α}} from prior
    │
    ├── config_gen.generate(base_config_path, params)
    │     └── writes a temp config.yaml with overridden w and α per plugin
    │
    ├── runner.run_batch(config_path, n_sims, base_seed)
    │     └── runs n_sims simulations (seed = base_seed + i)
    │     └── pools all clone sizes across runs into one flat list[float]
    │
    ├── distance.compute(simulated_pool, target_pool)
    │     └── pluggable — returns a scalar
    │
    └── if distance < ε → record (params, distance) as accepted
```

Accepted samples accumulate as `list[tuple[dict, float]]` — the ABC posterior approximation.


## 4. Pooling strategy

Each simulation returns `final_counts` (clone sizes excluding the founding `wt` clone).
Across `n_sims` runs, all non-wt clone sizes are concatenated into one flat array.
This pooled array is compared directly to the target distribution.
The loss function therefore operates on two flat arrays of clone sizes (raw cell counts).


## 5. Loss functions

```python
# calibration/distance.py

class Distance(ABC):
    @abstractmethod
    def compute(self, simulated: list[float], target: list[float]) -> float: ...

class L1Distance(Distance): ...         # mean absolute difference on sorted vectors
class L2Distance(Distance): ...         # RMSE on sorted vectors
class KSDistance(Distance): ...         # Kolmogorov-Smirnov statistic
class WassersteinDistance(Distance): ...  # Earth mover's distance (scipy)
```

The active distance class is selected by name in `calibration.yaml`.
Adding a new loss function = adding a new subclass, nothing else changes.


## 6. Calibration config

```yaml
# calibration.yaml
base_config: evoseer/config/default.yaml

n_samples: 500        # total ABC iterations
n_sims: 50            # simulations pooled per parameter set
epsilon: 0.1          # acceptance threshold
distance: ks          # Distance class to use: l1 | l2 | ks | wasserstein
base_seed: 42

target:
  data_dir: /path/to/ISIC_2024

priors:
  mapk:
    weight: [uniform, 0.0, 2.0]
    alpha:  [uniform, -1.0, 1.0]
  ois:
    weight: [uniform, -2.0, 0.0]
    alpha:  [uniform, -1.0, 1.0]
```

Each prior entry is `[distribution, low, high]`. Only `uniform` is needed for now.


## 7. Target loader

```python
# calibration/target.py
def load_target(cfg: dict) -> list[float]:
    DATA = Path(cfg["data_dir"])
    meta = pl.read_csv(DATA / "metadata.csv", columns=["isic_id", "tbp_lv_areaMM2"])
    sup  = pl.read_csv(DATA / "ISIC_2024_Training_Supplement.csv", columns=["isic_id", "iddx_1"])
    return (
        meta.join(sup, on="isic_id", how="left")
            .filter(pl.col("iddx_1") == "Benign")
            ["tbp_lv_areaMM2"]
            .drop_nulls()
            .to_list()
    )
```

Override this function directly if the data source changes — no YAML indirection needed.


## 8. Config generation

`config_gen.generate(base_config_path, params)` reads the base YAML, applies
`{plugin_name: {weight, alpha}}` overrides, and writes a uniquely named temp file
(e.g. `/tmp/evoseer_abc_{uuid}.yaml`). The temp file is deleted after the batch run.

The existing engine and `load_config` are used unchanged.


## 9. Output

`RejectionABC.run()` returns a `CalibrationResult`:

```python
@dataclass
class CalibrationResult:
    accepted: list[tuple[dict, float]]   # (params, distance) for accepted samples
    all_distances: list[float]           # distances for all iterations (for diagnostics)
    acceptance_rate: float
```

Results are serialisable to JSON for downstream analysis.


## 10. What stays unchanged

- `evoseer/` — untouched
- `evoseer/config/default.yaml` — used as the base config, never modified
- `main.py` — untouched
- All existing tests — unaffected

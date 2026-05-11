# Logistic Carrying Capacity Design

**Date:** 2026-05-08  
**Problem:** Population grows without bound until `max_cells`. Need logistic plateau controlled by a carrying capacity parameter.

## Solution Overview

Move density-dependent regulation from a separate `DummyDeathPlugin` into the core `RateFunctionConfig`. Users specify `carrying_capacity: K` directly; the code derives the density coefficient automatically.

Formula: `d = baseline_death + (baseline_birth - baseline_death)/K × N`

At equilibrium (WT, no mutations): `N_eq = K`

## Configuration Changes

### RateFunctionConfig

Add `carrying_capacity: float | None = None` to the dataclass:

```python
@dataclass
class RateFunctionConfig:
    function_type: str = "weighted_sum"
    baseline_birth_rate: float = 0.5
    baseline_death_rate: float = 0.2
    carrying_capacity: float | None = None  # New parameter
    params: dict[str, Any] = field(default_factory=dict)
```

In `load_config`, read carrying_capacity from YAML:

```python
rf_raw = raw.get("rate_function", {})
cfg.rate_function = RateFunctionConfig(
    function_type=rf_raw.get("type", "weighted_sum"),
    baseline_birth_rate=rf_raw.get("baseline_birth_rate", 0.5),
    baseline_death_rate=rf_raw.get("baseline_death_rate", 0.2),
    carrying_capacity=rf_raw.get("carrying_capacity", None),
    params={k: v for k, v in rf_raw.items() 
            if k not in {"type", "baseline_birth_rate", "baseline_death_rate", "carrying_capacity"}},
)
```

## WeightedSumRate Changes

In `__init__`, validate and derive density coefficient:

```python
def __init__(self, config: RateFunctionConfig) -> None:
    self._baseline_birth = config.baseline_birth_rate
    self._baseline_death = config.baseline_death_rate
    
    if config.carrying_capacity is not None:
        if config.carrying_capacity <= 0:
            raise ValueError(
                f"carrying_capacity must be > 0, got {config.carrying_capacity}. "
                "Use carrying_capacity: null (or omit) for unlimited growth."
            )
        self._density_coeff = (self._baseline_birth - self._baseline_death) / config.carrying_capacity
    else:
        self._density_coeff = 0.0
```

In `compute_rates`, add density term to death:

```python
death = self._baseline_death + self._density_coeff * N
```

## YAML Updates

### default.yaml (no regulation)
```yaml
rate_function:
  type: weighted_sum
  baseline_birth_rate: 0.5
  baseline_death_rate: 0.2
  # carrying_capacity omitted → unlimited growth
```

### erk_ois.yaml (plateau at 5000)
```yaml
rate_function:
  type: weighted_sum
  baseline_birth_rate: 0.8
  baseline_death_rate: 0.1
  carrying_capacity: 5000
```

Remove the `base_death: dummy_death` plugin from erk_ois.yaml.

## Backward Compatibility

- Configs without `carrying_capacity` work unchanged (default `None` → `density_coeff = 0`)
- No breaking changes to public APIs

## Testing

1. **Logistic plateau:** With K=5000, b=0.8, d=0.1 → population stabilizes at N ≈ 5000 (±10%)
2. **Unlimited growth:** Without K → population grows freely until `max_cells`
3. **Invalid K:** `carrying_capacity <= 0` → raises `ValueError` with helpful message
4. **Legacy configs:** Load without errors, behavior unchanged

# OIS (Oncogene-Induced Senescence) Plugin Design

**Date**: 2026-04-28
**Branch**: `pathways`

---

## Overview

OIS is modeled as two decoupled components inside a single `OISPlugin` that extends `PathwayPlugin`:

1. **S_i — Genotypic susceptibility** (Eq 2.9): same sigmoid/DFS machinery as `ErkPathwayPlugin`, with gene sets curated from the CellAge database.
2. **λ_i^OIS — Stochastic firing hazard** (Eq 2.10): `λ_i^OIS = S_i · λ₀ · Hill(k_i, K, n)` where `k_i` is the per-cell division counter since first OIS-triggering mutation (H2 hypothesis).

When the hazard fires, the cell is permanently marked senescent and its birth rate is forced to 0 (death rate unchanged, per Table 1 footnote).

---

## 1. Genotypic Susceptibility S_i

Follows the exact same formula and YAML structure as ERK:

$$
S_i = \sigma\!\left(\sum_{g \in \mathrm{OIS_{act}}} \omega_g \cdot x_g^{\mathrm{GOF}} - \sum_{g \in \mathrm{OIS_{inh}}} \omega_g \cdot x_g^{\mathrm{LOF}}\right) \in (0,1)
$$

- **OIS_act** (pro-senescence): genes whose GOF activates OIS — BRAF, NRAS, KRAS. Derived by DFS parity as in `ErkPathwayPlugin`.
- **OIS_inh** (anti-senescence): genes whose LOF *subtracts* from the sum (removes OIS machinery) — CDKN2A, TP53. These are **not** disinhibitors (additive LOF); they are explicit suppressors that reduce S_i when lost. Stored in a new `suppressors` block in the YAML.

Key values (placeholder; will be calibrated by ABC):
- WT cell: A = 0 → S_i = σ(0) = 0.5 (machinery armed but unengaged, threshold = 0)
- BRAF GOF: A = 0.50 → S_i → ~0.88
- BRAF GOF + CDKN2A LOF: A = 0.50 − 1.50 = −1.0 → S_i → ~0.07 (OIS escape)

### `suppressors` YAML extension

`PathwayDefinition` gains a new optional `suppressors` block — genes whose LOF subtracts from the weighted sum. This is orthogonal to `inh_R` (disinhibitors that add when LOF):

```yaml
suppressors:
  CDKN2A: { gene_id: 1029, weight: 1.50 }
  TP53:   { gene_id: 7157, weight: 0.50 }
```

`PathwayPlugin.compute_score()` adds one line: for LOF mutations in suppressors, subtract rather than add.

---

## 2. Stochastic Hazard λ_i^OIS (H2 — Division-Driven)

$$
\lambda_i^{\mathrm{OIS}}(t) = S_i \cdot \lambda_0 \cdot \mathrm{Hill}(k_i,\, K,\, n)
\qquad \mathrm{Hill}(u, K, n) = \frac{u^n}{K^n + u^n}
$$

- **k_i**: division counter since first OIS-triggering mutation (GOF in OIS_act gene). Starts at 0, increments at every division (+1 to both parent and child), resets to 0 when a new OIS-triggering mutation is acquired.
- **λ₀**: overall rate scale (YAML `ois.lambda_0`).
- **K**: half-saturation division count (YAML `ois.K_0`).
- **n**: Hill coefficient (YAML `ois.n`).

Hill(0, K, n) = 0, so a cell that has just acquired its first OIS-triggering mutation has zero hazard until it starts dividing.

---

## 3. OISPluginState

`OISPluginState` subclasses `PluginState` and adds three fields:

```python
@dataclass
class OISPluginState(PluginState):
    k:            int      = 0     # divisions since first OIS-triggering mutation
    t_trigger:    int|None = None  # step at which triggering mutation was acquired
    is_senescent: bool     = False
```

This is the canonical example of why `plugin_states` is a dict of subclassable objects: the counter and the flag must travel with the cell across divisions.

### Division propagation

`OISPlugin.on_division()`:
1. Increments `parent.k += 1` in-place.
2. Returns a child `OISPluginState` with `k = parent.k` (same post-increment value), `t_trigger = parent.t_trigger`, `is_senescent = False`.

### Mutation trigger

New `FeaturePlugin` hook: `on_mutation_acquired(mut_id, cell_state, step)` (default: no-op). `OISPlugin` overrides: if the mutation is a GOF in an OIS_act gene, reset `k = 0` and `t_trigger = step` on the child's plugin state.

---

## 4. New plugin target: `"senescence"`

Plugins with `target: "senescence"` are collected into `_senescence_plugins` in the engine (same pattern as `_rate_plugins`). They are never passed to `WeightedSumRate`. Instead:

- Their `compute_score()` result (= S_i) is cached normally via `_get_score()`.
- A new method `compute_senescence_hazard(cell_state, ctx) → float` returns λ_i^OIS using the cached S_i and the current k from `OISPluginState`.
- A new method `on_senescence(cell_state)` is called by the engine when the hazard fires; `OISPlugin` sets `ps.is_senescent = True`.

**`WeightedSumRate.compute_rates()`** gains `senescent: bool = False`. If True, returns `(0.0, baseline_death_rate)` immediately.

---

## 5. Engine changes (Gillespie)

Two generic additions (no biology hardcoded in the engine):

### Three-way event selection

```
for each cell:
    scores   = _get_all_scores(cell, ctx)     # rate_function + senescence plugins
    is_sen   = _is_senescent(cell)
    b, d     = rate_fn.compute_rates(rate_scores, configs, N, senescent=is_sen)
    ois      = 0.0 if is_sen else Σ plugin.compute_senescence_hazard(cell.state, ctx)
    λ_i      = b + d + ois

total Λ, Δt as before; event dispatch:
    r < b_i       → division
    r < b_i + d_i → death
    else          → senescence → plugin.on_senescence(cell.state) + record
```

### `on_mutation_acquired` hook

Called in `_execute_division()` after child mutations are assigned, for the child only:

```python
for mut_id in new_mutations:
    for plugin in self._plugins.values():
        plugin.on_mutation_acquired(mut_id, child.state, step)
```

---

## 6. Recorder

New event type:
```python
@dataclass(frozen=True)
class SenescenceEvent:
    step: int
    cell_id: int
```

`SimulationResult` gains `senescence: list[SenescenceEvent]`.

---

## 7. Files created / modified

| File | Action |
|------|--------|
| `evoseer/plugins/base.py` | + `on_mutation_acquired`, `on_senescence`, `compute_senescence_hazard` no-ops |
| `evoseer/plugins/pathway/__init__.py` | + `suppressors` in `PathwayDefinition`, subtract in `compute_score()` |
| `evoseer/plugins/ois/__init__.py` | new: `OISPluginState`, `OISPlugin` |
| `evoseer/plugins/ois/melanocyte.py` | new: `MelanocyteOISPlugin` (3 lines) |
| `evoseer/plugins/ois/data/melanocyte_ois.yaml` | new: gene weights + sigmoid + ois params |
| `evoseer/plugins/__init__.py` | register `MelanocyteOISPlugin` |
| `evoseer/rate_functions/weighted_sum.py` | + `senescent` param |
| `evoseer/engine/gillespie.py` | + `_senescence_plugins`, OIS hazard loop, hook call, senescence event |
| `evoseer/recording/recorder.py` | + `SenescenceEvent`, `result.senescence` |
| `tests/plugins/ois/test_ois_plugin.py` | new |
| `tests/engine/test_ois_integration.py` | new |

---

## 8. YAML — `melanocyte_ois.yaml`

```yaml
name: OIS
kegg_id: ~
description: "Oncogene-Induced Senescence pathway in melanocytes"

output_node: CDKN2A

sigmoid:
  slope: 4.0
  threshold: 0.0   # WT cell: A=0 → S_i = σ(0) = 0.5

ois:
  lambda_0: 0.01
  K_0: 15.0
  n: 2

nodes:
  BRAF:   { gene_id: 673,  weight: 0.50 }
  NRAS:   { gene_id: 4893, weight: 0.20 }
  KRAS:   { gene_id: 3845, weight: 0.05 }
  CDKN2A: { gene_id: 1029, weight: 0.10 }   # included as output node

edges:
  - { from: BRAF,   to: CDKN2A, type: activates }
  - { from: NRAS,   to: CDKN2A, type: activates }
  - { from: KRAS,   to: CDKN2A, type: activates }

suppressors:
  CDKN2A: { gene_id: 1029, weight: 1.50 }   # LOF → S_i ↓ (OIS escape)
  TP53:   { gene_id: 7157, weight: 0.50 }
```

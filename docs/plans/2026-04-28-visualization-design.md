# Visualization Design

**Date**: 2026-04-28
**Branch**: `viz`

---

## Overview

Export simulation results from Python as a structured JSON file, then visualize them in the site's existing Visualizer page with two views: a fishplot (clonal fractions over time) and a clone time-tree (phylogenetic tree with clone sizes).

---

## 1. Export format — `*.evoseer.json`

```json
{
  "metadata": {
    "seed": 10,
    "stop_reason": "max_cells",
    "simulation": {
      "max_steps": 10000,
      "max_time": 1e9,
      "max_cells": 2000
    },
    "rate_function": {
      "type": "weighted_sum",
      "baseline_birth_rate": 0.5,
      "baseline_death_rate": 0.2
    },
    "mutation_generator": {
      "type": "uniform",
      "params": { "seed": 10 }
    },
    "plugins": [
      {
        "name": "erk_pathway",
        "type": "erk_pathway",
        "target": "rate_function",
        "category": "proliferative",
        "weight": 5.0,
        "alpha": 1.0,
        "params": {}
      }
    ]
  },
  "snapshots": [
    { "step": 0, "t": 0.052, "n_alive": 10, "n_dead_cumulative": 0 }
  ],
  "clonal_fractions": [
    { "step": 0,   "t": 0.052, "wt": 10,  "20004": 0, "20003": 0 },
    { "step": 400, "t": 0.057, "wt": 297, "20004": 3, "20003": 0 }
  ],
  "clone_tree": {
    "nodes": [
      {
        "id": "wt",
        "label": "Founding clone",
        "gene": null,
        "effect": null,
        "acq_step": 0,
        "acq_t": 0.0,
        "final_size": 1997
      },
      {
        "id": "20004",
        "label": "NRAS GOF #2",
        "gene": "NRAS",
        "effect": "GOF",
        "acq_step": 305,
        "acq_t": 0.057,
        "final_size": 2
      }
    ],
    "edges": [
      { "parent": "wt", "child": "20004" }
    ]
  }
}
```

**Key design choices:**
- `clonal_fractions`: each snapshot row has one key per clone (`wt` for founding clone, `mutation_id` as string for drivers). A cell belongs to the **first driver it carries in acquisition order** (same logic as notebook).
- `clone_tree` parent-child: clone B is child of A if the cell that acquired mutation B was already in clone A at the time of acquisition (temporal/biological definition). Determined by inspecting `cell_drivers[cell_id]` just before the DriverEvent.
- `metadata.plugins` is serialized from `PluginConfig` dataclasses — no new config fields needed.
- `seed` is surfaced at top-level of `metadata` for easy reproducibility.

---

## 2. Python exporter — `evoseer/recording/exporter.py`

```python
class SimulationExporter:
    def __init__(
        self,
        result: SimulationResult,
        store: MutationStore,
        config: SimulationConfig | None = None,
    ): ...

    def export(self) -> dict: ...
    def save(self, path: str | Path) -> None: ...

    def _build_metadata(self) -> dict: ...
    def _build_clonal_fractions(self) -> list[dict]: ...
    def _build_clone_tree(self) -> dict: ...
```

**`_build_clonal_fractions` + `_build_clone_tree` share one pass** over events:

```
Build: div_by_step, death_by_step, driver_by_step
       cell_drivers: dict[cell_id, set[mut_id]]
       alive_cells: set[int]
       driver_acq_order: list[mut_id]   ← chronological

For each snapshot (sorted by step):
  advance cur_step → snap.step:
    - divisions: child inherits parent's drivers
    - deaths: remove from alive
    - drivers: add mut_id to cell's set
              → record parent clone for tree edge
  count alive cells per clone key → clonal_fractions row
```

Clone parent resolution at driver acquisition:
```
cell acquires mut B at step S
parent_clone = first mut in driver_acq_order that cell already carries
             = "wt" if cell carries no drivers yet
```

**Tests** in `tests/recording/test_exporter.py`:
- Export round-trips correctly (known seed, check clone counts)
- Clone tree edges are correct for nested vs independent acquisitions
- Works with `config=None` (programmatic runs)

---

## 3. Site visualizer

### Layout

The existing `Visualizer.astro` parses the `.evoseer.json` and renders two tabs:

```
┌─────────────────────────────────────────────┐
│ [Fishplot]  [Clone Tree]          my_run.json│
├─────────────────────────────────────────────┤
│                                             │
│  (active tab content)                       │
│                                             │
└─────────────────────────────────────────────┘
```

### Tab 1 — Fishplot (`FishplotChart.astro`)

- Uses `CanvasChart` + new `stackplot(series, colors)` method in `canvas-chart.ts`
- X axis: simulated time, Y axis: N cells (toggle to fraction)
- One filled area per clone, stacked, colors by gene (BRAF blue, NRAS green, NF1 orange, wt gray)
- Star markers (★) at driver acquisition times, as in the notebook

### Tab 2 — Clone time-tree (`CloneTreeChart.astro`)

- SVG layout (more natural than canvas for hierarchical/interactive elements)
- X axis: simulated time
- Each clone = horizontal line starting at `acq_t`, ending at simulation end
- Parent→child connected by a vertical line at the child's `acq_t`
- Terminal circle: radius ∝ √`final_size`, color by gene
- Tooltip on hover: label, final_size, acq_step

```
wt      ────────────────────────────────● (r∝√1997)
              │
              └── NRAS GOF #2 ─────────● (r∝√2)
                       │
                       └── NRAS GOF #1 ─● (r∝√1)
        t=0           t=0.057  t=0.059
```

---

## 4. Files created / modified

| File | Action |
|------|--------|
| `evoseer/recording/exporter.py` | new |
| `tests/recording/test_exporter.py` | new |
| `site/src/utils/canvas-chart.ts` | +`stackplot()` |
| `site/src/components/FishplotChart.astro` | new |
| `site/src/components/CloneTreeChart.astro` | new |
| `site/src/components/Visualizer.astro` | updated (tabs + parsing) |

All work on branch `viz`, branched from `pathways`.

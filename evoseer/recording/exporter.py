"""Export a SimulationResult to the *.evoseer.json format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from evoseer.core.config import SimulationConfig
from evoseer.recording.recorder import SimulationResult
from evoseer.services.mutation_store import MutationStore


class SimulationExporter:
    """
    Convert a SimulationResult + MutationStore into the *.evoseer.json export format.

    All heavy lifting (lineage reconstruction) happens in a single pass shared
    between clonal_fractions and clone_tree outputs.
    """

    def __init__(
        self,
        result: SimulationResult,
        store: MutationStore,
        config: SimulationConfig | None = None,
    ) -> None:
        self.result = result
        self.store = store
        self.config = config
        self._lineage_cache: _LineageState | None = None

    def export(self) -> dict:
        state = self._build_lineage()
        return {
            "metadata": self._build_metadata(),
            "snapshots": _build_snapshots(self.result),
            "clonal_fractions": state.clonal_fractions,
            "clone_tree": self._build_clone_tree(state),
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.export(), indent=2))

    # ── Metadata ────────────────────────────────────────────────────────────

    def _build_metadata(self) -> dict:
        meta: dict[str, Any] = {"stop_reason": self.result.stop_reason}
        if self.config is None:
            return meta
        meta["seed"] = self.config.seed
        meta["simulation"] = {
            "max_steps": self.config.max_steps,
            "max_time": self.config.max_time,
            "max_cells": self.config.max_cells,
        }
        meta["rate_function"] = {
            "type": self.config.rate_function.function_type,
            "baseline_birth_rate": self.config.rate_function.baseline_birth_rate,
            "baseline_death_rate": self.config.rate_function.baseline_death_rate,
            **self.config.rate_function.params,
        }
        meta["mutation_generator"] = {
            "type": self.config.mutation_generator.generator_type,
            "params": self.config.mutation_generator.params,
        }
        meta["plugins"] = [
            {
                "name": pc.name,
                "type": pc.plugin_type,
                "target": pc.target,
                "category": pc.category,
                "weight": pc.weight,
                "alpha": pc.alpha,
                "params": pc.params,
            }
            for pc in self.config.plugins
        ]
        return meta

    # ── Shared lineage pass ──────────────────────────────────────────────────

    def _build_lineage(self) -> _LineageState:
        if self._lineage_cache is not None:
            return self._lineage_cache

        result = self.result

        # Index events by step
        div_by_step: dict[int, list[tuple[int, int]]] = {}
        for ev in result.divisions:
            div_by_step.setdefault(ev.step, []).append((ev.parent_id, ev.child_id))

        death_by_step: dict[int, list[int]] = {}
        for ev in result.deaths:
            death_by_step.setdefault(ev.step, []).append(ev.cell_id)

        driver_by_step: dict[int, list[tuple[int, int]]] = {}
        for ev in result.drivers:
            driver_by_step.setdefault(ev.step, []).append((ev.cell_id, ev.mutation_id))

        sen_by_step: dict[int, list[int]] = {}
        for ev in result.senescence:
            sen_by_step.setdefault(ev.step, []).append(ev.cell_id)

        # step -> t interpolator from snapshots
        interp_t = _make_time_interpolator(result.snapshots)

        # Founder cells: parents never born as children
        all_children = {ev.child_id for ev in result.divisions}
        all_parents  = {ev.parent_id for ev in result.divisions}
        founder_ids  = all_parents - all_children
        if not founder_ids:
            # No divisions recorded — seed from driver + death events
            founder_ids = (
                {ev.cell_id for ev in result.drivers}
                | {ev.cell_id for ev in result.deaths}
            )

        # Mutable lineage state.
        # cell_clone_events maps cell_id -> set of clone event IDs the cell carries.
        # A clone event ID is unique per acquisition event (f"{mutation_id}_{counter}"),
        # so two independent acquisitions of the same mutation_id create distinct clones.
        cell_clone_events: dict[int, set[str]] = {fid: set() for fid in founder_ids}
        alive_cells:       set[int]             = set(founder_ids)
        senescent_cells:   set[int]             = set()
        driver_acq_order:    list[str]           = []  # clone event IDs, chronological
        driver_acq_step:     dict[str, int]      = {}  # clone_id -> step
        driver_parent_clone: dict[str, str]      = {}  # clone_id -> parent clone_id
        clone_mutation:      dict[str, int]      = {}  # clone_id -> mutation_id
        _acq_counter:        dict[int, int]      = {}  # mutation_id -> # times acquired

        # Snapshot-step-ordered collection points
        snap_by_step = {s.step: s for s in result.snapshots}
        snapshot_steps = sorted(snap_by_step)
        clonal_fractions: list[dict] = []

        cur_step = 0

        def _advance_to(target: int) -> None:
            nonlocal cur_step
            while cur_step <= target:
                for parent_id, child_id in div_by_step.get(cur_step, []):
                    cell_clone_events[child_id] = set(cell_clone_events.get(parent_id, ()))
                    alive_cells.add(child_id)
                for cid in death_by_step.get(cur_step, []):
                    alive_cells.discard(cid)
                    senescent_cells.discard(cid)
                for cid in sen_by_step.get(cur_step, []):
                    if cid in alive_cells:
                        senescent_cells.add(cid)
                for cid, mid in driver_by_step.get(cur_step, []):
                    if cid not in cell_clone_events:
                        cell_clone_events[cid] = set()
                    # Each acquisition event creates a new clone regardless of mutation_id
                    idx = _acq_counter.get(mid, 0)
                    _acq_counter[mid] = idx + 1
                    clone_id = f"{mid}_{idx}"
                    # Parent clone = earliest clone this cell already carries
                    parent = "wt"
                    for prev_id in driver_acq_order:
                        if prev_id in cell_clone_events[cid]:
                            parent = prev_id
                            break
                    driver_parent_clone[clone_id] = parent
                    driver_acq_step[clone_id] = cur_step
                    driver_acq_order.append(clone_id)
                    clone_mutation[clone_id] = mid
                    cell_clone_events[cid].add(clone_id)
                cur_step += 1

        for snap_step in snapshot_steps:
            _advance_to(snap_step)
            snap = snap_by_step[snap_step]
            row: dict[str, Any] = {"step": snap_step, "t": snap.t}
            row.update(_count_clones(alive_cells, cell_clone_events, driver_acq_order))
            sen_counts = _count_clones(senescent_cells, cell_clone_events, driver_acq_order)
            for k, v in sen_counts.items():
                row[k + "_sen"] = v
            clonal_fractions.append(row)

        # Advance past all driver events so tree metadata is complete
        all_driver_steps = list(driver_by_step)
        if all_driver_steps:
            _advance_to(max(all_driver_steps))

        final_counts = _count_clones(alive_cells, cell_clone_events, driver_acq_order)

        self._lineage_cache = _LineageState(
            clonal_fractions=clonal_fractions,
            driver_acq_order=driver_acq_order,
            driver_acq_step=driver_acq_step,
            driver_parent_clone=driver_parent_clone,
            clone_mutation=clone_mutation,
            final_counts=final_counts,
            interp_t=interp_t,
        )
        return self._lineage_cache

    def _build_clone_tree(self, state: _LineageState) -> dict:
        nodes: list[dict] = [
            {
                "id": "wt",
                "label": "Founding clone",
                "gene": None,
                "effect": None,
                "acq_step": 0,
                "acq_t": 0.0,
                "final_size": state.final_counts.get("wt", 0),
            }
        ]
        edges: list[dict] = []

        for clone_id in state.driver_acq_order:
            mid = state.clone_mutation[clone_id]
            try:
                rec = self.store.get(mid)
                gene   = rec.gene_name
                effect = rec.effect
                label  = _driver_label(rec, mid)
            except KeyError:
                gene   = None
                effect = None
                label  = f"Driver {mid}"

            acq_step = state.driver_acq_step[clone_id]
            nodes.append(
                {
                    "id": clone_id,
                    "label": label,
                    "mutation_id": mid,
                    "gene": gene,
                    "effect": effect,
                    "acq_step": acq_step,
                    "acq_t": state.interp_t(acq_step),
                    "final_size": state.final_counts.get(clone_id, 0),
                }
            )
            edges.append({"parent": state.driver_parent_clone[clone_id], "child": clone_id})

        return {"nodes": nodes, "edges": edges}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_snapshots(result: SimulationResult) -> list[dict]:
    return [
        {
            "step": s.step,
            "t": s.t,
            "n_alive": s.n_alive,
            "n_dead_cumulative": s.n_dead_cumulative,
        }
        for s in result.snapshots
    ]


def _count_clones(
    alive_cells: set[int],
    cell_clone_events: dict[int, set[str]],
    acq_order: list[str],
) -> dict[str, int]:
    """Count alive cells per clone.

    Clone identity is determined by the *earliest-acquired clone event* the cell carries,
    not by mutation_id alone — two independent acquisitions of the same mutation produce
    distinct clone event IDs and are counted separately.
    """
    counts: dict[str, int] = {"wt": 0}
    for cid in alive_cells:
        carried = cell_clone_events.get(cid, ())
        key = "wt"
        # Iterate most-recently-acquired first so a cell carrying both a parent
        # clone and a subclone is assigned to the most derived clone.
        for clone_id in reversed(acq_order):
            if clone_id in carried:
                key = clone_id
                break
        counts[key] = counts.get(key, 0) + 1
    return counts


def _driver_label(rec: Any, mid: int) -> str:
    gene = rec.gene_name or (f"gene_{rec.gene_id}" if rec.gene_id else f"mut_{mid}")
    effect = rec.effect or "?"
    return f"{gene} {effect}"


def _make_time_interpolator(
    snapshots: list,
) -> Callable[[int], float]:
    if not snapshots:
        return lambda _step: 0.0
    sorted_snaps = sorted(snapshots, key=lambda s: s.step)
    step_to_t = {s.step: s.t for s in sorted_snaps}

    def interp(step: int) -> float:
        if step in step_to_t:
            return step_to_t[step]
        lo = hi = None
        for s in sorted_snaps:
            if s.step <= step:
                lo = s
            else:
                hi = s
                break
        if lo is None:
            return sorted_snaps[0].t
        if hi is None:
            return lo.t
        frac = (step - lo.step) / (hi.step - lo.step)
        return lo.t + frac * (hi.t - lo.t)

    return interp


class _LineageState:
    __slots__ = (
        "clonal_fractions",
        "driver_acq_order",
        "driver_acq_step",
        "driver_parent_clone",
        "clone_mutation",
        "final_counts",
        "interp_t",
    )

    def __init__(
        self,
        clonal_fractions: list[dict],
        driver_acq_order: list[str],
        driver_acq_step: dict[str, int],
        driver_parent_clone: dict[str, str],
        clone_mutation: dict[str, int],
        final_counts: dict[str, int],
        interp_t: Callable[[int], float],
    ) -> None:
        self.clonal_fractions    = clonal_fractions
        self.driver_acq_order    = driver_acq_order
        self.driver_acq_step     = driver_acq_step
        self.driver_parent_clone = driver_parent_clone
        self.clone_mutation      = clone_mutation
        self.final_counts        = final_counts
        self.interp_t            = interp_t

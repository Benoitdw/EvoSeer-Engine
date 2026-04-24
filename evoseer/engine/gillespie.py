"""GillespieEngine — biology-agnostic stochastic simulation loop."""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from evoseer.core.cell import Cell, CellState
from evoseer.core.config import PluginConfig, SimulationConfig
from evoseer.core.context import SimContext
from evoseer.plugins.base import FeaturePlugin
from evoseer.rate_functions.base import RateFunction
from evoseer.recording.recorder import Recorder, SimulationResult
from evoseer.services.mutation_generator import MutationGenerator
from evoseer.services.mutation_store import MutationStore


class GillespieEngine:
    """
    Biology-agnostic stochastic evolutionary simulation engine.

    Orchestrates the Gillespie algorithm over a population of cells. The
    engine knows nothing about biology — it only sees cells, numeric scores,
    and rates. All biological logic lives in FeaturePlugin implementations.

    Step flow (design doc §7.2):
        1. Collect scores for every living cell / rate_function plugin.
        2. Compute per-cell (birth, death) rates via the RateFunction.
        3. Draw waiting time Δt ~ Exp(Λ).
        4. Select a cell proportional to its total rate λ_i.
        5. Select event: division or death.
        6. Execute event, assign new mutations, mark dirty plugins.
        7. Record snapshot every ``snapshot_interval`` steps.
    """

    def __init__(
        self,
        plugins: dict[str, FeaturePlugin],
        plugin_configs: dict[str, PluginConfig],
        rate_function: RateFunction,
        mutation_generator: MutationGenerator,
        store: MutationStore,
        recorder: Recorder,
        config: SimulationConfig,
    ) -> None:
        self._plugins = plugins
        self._plugin_configs = plugin_configs
        self._rate_fn = rate_function
        self._mut_gen = mutation_generator
        self._store = store
        self._recorder = recorder
        self._config = config

        # Separate rate_function plugins from the mutation_rate plugin
        self._rate_plugins: dict[str, FeaturePlugin] = {
            name: p
            for name, p in plugins.items()
            if plugin_configs.get(name) and plugin_configs[name].target == "rate_function"
        }
        self._mutation_rate_plugin: FeaturePlugin | None = next(
            (
                p
                for name, p in plugins.items()
                if plugin_configs.get(name)
                and plugin_configs[name].target == "mutation_rate"
            ),
            None,
        )

        seed = config.seed
        self._rng = np.random.default_rng(seed)

        self._next_id: int = 0
        self._cells: dict[int, Cell] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, initial_cells: list[Cell]) -> SimulationResult:
        """
        Run the full simulation starting from ``initial_cells``.

        Returns a SimulationResult produced by the Recorder.
        """
        for cell in initial_cells:
            self._cells[cell.id] = cell
            self._next_id = max(self._next_id, cell.id + 1)

        t = 0.0
        step = 0
        stop_reason = "max_steps"

        while True:
            N = len(self._cells)

            # --- stopping conditions ---
            if step >= self._config.max_steps:
                stop_reason = "max_steps"
                break
            if t >= self._config.max_time:
                stop_reason = "max_time"
                break
            if N >= self._config.max_cells:
                stop_reason = "max_cells"
                break
            if N == 0:
                stop_reason = "extinction"
                break

            ctx = SimContext(t=t, step=step, N=N)

            # 1. Collect scores and compute per-cell rates
            cell_list = list(self._cells.values())
            birth_rates: list[float] = []
            death_rates: list[float] = []

            for cell in cell_list:
                scores = self._get_scores(cell, ctx)
                b, d = self._rate_fn.compute_rates(scores, self._plugin_configs, N)
                birth_rates.append(b)
                death_rates.append(d)

            total_rates = [b + d for b, d in zip(birth_rates, death_rates)]

            # 2. Total rate Λ
            Lambda = sum(total_rates)
            if Lambda <= 0.0:
                stop_reason = "zero_rate"
                break

            # 3. Draw waiting time
            dt = -math.log(self._rng.random()) / Lambda
            t += dt
            step += 1

            # 4. Select cell proportional to λ_i
            probs = [r / Lambda for r in total_rates]
            cell_idx: int = self._rng.choice(len(cell_list), p=probs)
            selected_cell = cell_list[cell_idx]
            b_i = birth_rates[cell_idx]
            d_i = death_rates[cell_idx]
            lambda_i = b_i + d_i

            # 5. Select event
            if self._rng.random() < b_i / lambda_i:
                self._execute_division(selected_cell, step, ctx)
            else:
                self._execute_death(selected_cell, step)

            # 7. Snapshot
            self._recorder.maybe_snapshot(step, t, len(self._cells))

        return self._recorder.finalise(self._cells, stop_reason)

    # ------------------------------------------------------------------
    # Score helpers
    # ------------------------------------------------------------------

    def _get_score(self, cell: Cell, plugin: FeaturePlugin, ctx: SimContext) -> float:
        """
        Return the cached score for a plugin, recomputing if dirty.

        This implements the cache check described in design doc §4.3.
        """
        ps = cell.state.plugin_states.get(plugin.name)
        if ps is None:
            # Lazily initialise state if missing (shouldn't happen after proper setup)
            ps = plugin.init_state(cell.state, ctx)
            cell.state.plugin_states[plugin.name] = ps

        if ps._dirty:
            ps._cached_score = plugin.compute_score(cell.state, ctx)
            ps._dirty = False

        return ps._cached_score  # type: ignore[return-value]

    def _get_scores(self, cell: Cell, ctx: SimContext) -> dict[str, float]:
        """Collect scores for all rate_function-targeted plugins."""
        return {
            name: self._get_score(cell, plugin, ctx)
            for name, plugin in self._rate_plugins.items()
        }

    def _get_mutation_rate(self, cell: Cell, ctx: SimContext) -> float:
        """Return μ from the mutation_rate plugin, defaulting to 0."""
        if self._mutation_rate_plugin is None:
            return 0.0
        return self._get_score(cell, self._mutation_rate_plugin, ctx)

    # ------------------------------------------------------------------
    # Event execution
    # ------------------------------------------------------------------

    def _execute_death(self, cell: Cell, step: int) -> None:
        """Remove cell from active pool and update parent lineage."""
        cell.alive = False
        del self._cells[cell.id]

        # Purge from parent's children list
        if cell.parent_id is not None and cell.parent_id in self._cells:
            parent = self._cells[cell.parent_id]
            try:
                parent.children_ids.remove(cell.id)
            except ValueError:
                pass

        self._recorder.record_death(step, cell.id)

    def _execute_division(self, parent: Cell, step: int, ctx: SimContext) -> None:
        """
        Divide parent: call on_division on all plugins, assign new mutations,
        mark dirty for affected plugins, register child in the active pool.
        """
        # a. Call on_division on all plugins → parent mutated in place, child state built
        child_plugin_states: dict[str, Any] = {}
        for name, plugin in self._plugins.items():
            if name not in parent.state.plugin_states:
                parent.state.plugin_states[name] = plugin.init_state(parent.state, ctx)

            child_plugin_states[name] = plugin.on_division(parent.state, ctx)

        # b–d. Get μ_i and delegate count + ID sampling entirely to the generator
        mu_i = self._get_mutation_rate(parent, ctx)
        new_mutations = self._mut_gen.generate(mu_i)

        # e. Create child cell inheriting parent mutations + new ones
        child_mutations = set(parent.state.mutations) | set(new_mutations)
        child_state = CellState(
            mutations=child_mutations,
            plugin_states=child_plugin_states,
        )
        child_id = self._next_id
        self._next_id += 1
        child = Cell(
            cell_id=child_id,
            birth_step=step,
            state=child_state,
            parent_id=parent.id,
        )
        parent.children_ids.append(child_id)
        self._cells[child_id] = child

        # f. Mark dirty on plugins whose pathways intersect with new mutations
        for mut_id in new_mutations:
            pathways = self._store.get_gene_pathways(mut_id)
            if not pathways:
                continue
            pathway_set = set(pathways)
            for name, plugin in self._plugins.items():
                if set(plugin.involved_pathways) & pathway_set:
                    for target_cell in (parent, child):
                        ps = target_cell.state.plugin_states.get(name)
                        if ps is not None:
                            ps.mark_dirty()

        # g. Record driver acquisitions
        for mut_id in new_mutations:
            if self._store.is_driver(mut_id):
                self._recorder.record_driver(step, child_id, mut_id)

        # h. Record division
        self._recorder.record_division(step, parent.id, child_id)

    # ------------------------------------------------------------------
    # Cell factory (used to build the initial population)
    # ------------------------------------------------------------------

    def make_founder_cell(self, ctx: SimContext | None = None) -> Cell:
        """
        Create a founder cell with all plugins initialised.

        If ctx is None a zero-context is used (t=0, step=0, N=1).
        """
        if ctx is None:
            ctx = SimContext(t=0.0, step=0, N=1)

        state = CellState()
        for name, plugin in self._plugins.items():
            state.plugin_states[name] = plugin.init_state(state, ctx)

        cell_id = self._next_id
        self._next_id += 1
        return Cell(cell_id=cell_id, birth_step=0, state=state)

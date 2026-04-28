"""OISPlugin — Oncogene-Induced Senescence pathway plugin."""

from __future__ import annotations

import math
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from evoseer.core.cell import CellState, PluginState
from evoseer.core.context import SimContext
from evoseer.plugins.pathway import PathwayPlugin
from evoseer.services.mutation_store import MutationStore


@dataclass
class OISPluginState(PluginState):
    """
    Per-cell OIS state.

    k            -- divisions undergone since first OIS-triggering mutation
    t_trigger    -- step at which the first OIS-triggering mutation was acquired
    is_senescent -- True once the OIS hazard has fired for this cell

    This is the canonical example of PluginState subclassing: k and
    is_senescent must travel with the cell across divisions and cannot be
    derived from the mutation set alone.
    """

    k: int = 0
    t_trigger: int | None = None
    is_senescent: bool = False


class OISPlugin(PathwayPlugin, ABC):
    """
    Abstract base for OIS pathway plugins.

    Subclasses define:
        name            -- runtime identifier
        pathway_file    -- Path to the OIS YAML definition
        involved_pathways -- ["OIS"] (or equivalent)

    Inherits from PathwayPlugin: YAML loading, DFS role derivation, and
    sigmoid scoring for S_i are all provided by the parent class.

    Adds:
        OISPluginState per cell (k, t_trigger, is_senescent)
        on_division()        -- increments k on parent, propagates to child
        on_mutation_acquired() -- resets k when a new OIS-triggering mutation is acquired
        compute_senescence_hazard() -- λ_i^OIS = S_i · λ₀ · Hill(k, K, n)
        on_senescence()      -- sets is_senescent = True
    """

    def __init__(self, params: dict[str, Any], store: MutationStore) -> None:
        super().__init__(params, store)
        ois_block = self._definition.__dict__.get("_ois_params") or {}
        # Load OIS-specific params from YAML (stored under the 'ois' key)
        raw = _load_ois_params(self.pathway_file)
        self._ois_lambda_0: float = float(raw.get("lambda_0", 0.01))
        self._ois_K: float = float(raw.get("K_0", 15.0))
        self._ois_n: float = float(raw.get("n", 2.0))

    # ── PluginState lifecycle ────────────────────────────────────────────────

    def init_state(self, cell_state: CellState, ctx: SimContext) -> OISPluginState:
        return OISPluginState()

    def on_division(self, parent_state: CellState, ctx: SimContext) -> OISPluginState:
        parent_ps = parent_state.plugin_states.get(self.name)
        if not isinstance(parent_ps, OISPluginState):
            return OISPluginState()

        # Both parent and child get k + 1 (each chromosomal copy has undergone
        # the same number of replication events)
        parent_ps.k += 1

        return OISPluginState(
            k=parent_ps.k,
            t_trigger=parent_ps.t_trigger,
            is_senescent=False,  # children are never born senescent
            _cached_score=parent_ps._cached_score,
            _dirty=parent_ps._dirty,
        )

    # ── New hooks ────────────────────────────────────────────────────────────

    def on_mutation_acquired(
        self, mut_id: int, cell_state: CellState, step: int
    ) -> None:
        """Reset k to 0 when the cell acquires a new OIS-triggering mutation."""
        try:
            record = self._store.get(mut_id)
        except KeyError:
            return
        if record.effect != "GOF":
            return

        # Check if the gene is in OIS_act (activators of OIS)
        is_triggering = False
        if record.gene_id is not None:
            is_triggering = record.gene_id in self._act_by_id
        elif record.gene_name is not None:
            is_triggering = record.gene_name in self._act

        if is_triggering:
            ps = cell_state.plugin_states.get(self.name)
            if isinstance(ps, OISPluginState):
                ps.k = 0
                ps.t_trigger = step
                ps.mark_dirty()

    def compute_senescence_hazard(
        self, cell_state: CellState, ctx: SimContext
    ) -> float:
        """λ_i^OIS = S_i · λ₀ · Hill(k, K, n)."""
        ps = cell_state.plugin_states.get(self.name)
        if not isinstance(ps, OISPluginState):
            return 0.0
        if ps.is_senescent or ps.t_trigger is None or ps.k == 0:
            return 0.0

        s_i = ps._cached_score
        if s_i is None:
            return 0.0

        k = ps.k
        K = self._ois_K
        n = self._ois_n
        hill = (k ** n) / (K ** n + k ** n)
        return s_i * self._ois_lambda_0 * hill

    def on_senescence(self, cell_state: CellState) -> None:
        """Mark the cell as permanently senescent."""
        ps = cell_state.plugin_states.get(self.name)
        if isinstance(ps, OISPluginState):
            ps.is_senescent = True


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_ois_params(pathway_file: Path) -> dict:
    import yaml
    with open(pathway_file) as f:
        data = yaml.safe_load(f)
    return data.get("ois", {})

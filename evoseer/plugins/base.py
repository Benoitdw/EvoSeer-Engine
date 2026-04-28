"""FeaturePlugin ABC — base class for all biological feature plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from evoseer.core.cell import CellState, PluginState
from evoseer.core.context import SimContext
from evoseer.services.mutation_store import MutationRecord, MutationStore

_MISSING = object()


class FeaturePlugin(ABC):
    """
    Abstract base class for biological feature plugins.

    Subclasses must define:
        name              -- unique string identifier, matches the YAML key
        involved_pathways -- pathway names that trigger a score recompute

    Only compute_score is abstract. init_state and on_division have sensible
    defaults and only need to be overridden when custom per-cell state is required.

    The store is injected at construction and available as self._store.
    Use get_param() and get_extra() for validated access to config and
    mutation annotation fields.
    """

    name: str
    involved_pathways: list[str] = []

    def __init__(self, params: dict[str, Any], store: MutationStore) -> None:
        self._params = params
        self._store = store

    # ------------------------------------------------------------------
    # Plugin interface
    # ------------------------------------------------------------------

    def init_state(self, cell_state: CellState, ctx: SimContext) -> PluginState:
        """Return a fresh PluginState. Override only when custom state is needed."""
        return PluginState()

    @abstractmethod
    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        """Compute and return the plugin score for a cell."""
        ...

    def on_mutation_acquired(
        self, mut_id: int, cell_state: CellState, step: int
    ) -> None:
        """Called after a new mutation is assigned to a cell. Override to react."""

    def compute_senescence_hazard(
        self, cell_state: CellState, ctx: SimContext
    ) -> float:
        """Return λ_i^OIS for senescence-target plugins. Default: 0."""
        return 0.0

    def on_senescence(self, cell_state: CellState) -> None:
        """Called when this plugin's senescence hazard fires. Override to set flags."""

    def on_division(self, parent_state: CellState, ctx: SimContext) -> PluginState:
        """
        Handle a division event. Mutate parent_state in place if needed.

        Returns the child's PluginState, initialised with the parent's cached
        score so no recomputation is needed unless a new mutation hits a
        relevant pathway.
        """
        parent_ps = parent_state.plugin_states.get(self.name, PluginState())
        cached = parent_ps._cached_score
        return PluginState(_cached_score=cached, _dirty=cached is None)

    # ------------------------------------------------------------------
    # Validated accessors
    # ------------------------------------------------------------------

    def get_param(self, key: str, default: Any = _MISSING) -> Any:
        """Return a config param, raising a clear KeyError if absent."""
        if key not in self._params:
            if default is _MISSING:
                raise KeyError(
                    f"Plugin '{self.name}' requires param '{key}' "
                    f"but it was not found in config."
                )
            return default
        return self._params[key]

    def get_extra(self, record: MutationRecord, key: str) -> Any:
        """Return an extra field from a MutationRecord, raising a clear KeyError if absent."""
        if key not in record.extra:
            raise KeyError(
                f"Plugin '{self.name}' requires extra field '{key}' "
                f"on MutationRecord(id={record.mutation_id}, gene={record.gene_name})."
            )
        return record.extra[key]

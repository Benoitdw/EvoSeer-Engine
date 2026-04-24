"""Core data structures: Cell, CellState, PluginState."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PluginState:
    """
    Per-cell state managed by a FeaturePlugin.

    Subclass this to add plugin-specific fields. The dirty/cache mechanism
    avoids recomputing scores at every Gillespie step — a score is only
    recomputed when the cell's state has changed in a way that affects the
    plugin (new mutation in a relevant pathway, or a division event).
    """

    _cached_score: float | None = field(default=None, repr=False)
    _dirty: bool = field(default=True, repr=False)

    @property
    def score(self) -> float | None:
        """Return the cached score, or None if dirty (recomputation pending)."""
        return self._cached_score

    def mark_dirty(self) -> None:
        """Flag the cached score as stale so it is recomputed on next access."""
        self._dirty = True


@dataclass
class CellState:
    """
    Biological state of a cell, decoupled from identity and lineage.

    Holds the set of mutation IDs the cell carries, plus a per-plugin state
    object for every active FeaturePlugin.
    """

    mutations: set[int] = field(default_factory=set)
    plugin_states: dict[str, PluginState] = field(default_factory=dict)


class Cell:
    """
    A single cell in the simulation — identity, lineage, and biological state.

    The engine assigns monotonically increasing IDs. Lineage pointers
    (parent_id, children_ids) are maintained only for *living* cells; the
    Recorder's event log is the authoritative source for the full phylogeny.
    """

    def __init__(
        self,
        cell_id: int,
        birth_step: int,
        state: CellState,
        parent_id: int | None = None,
    ) -> None:
        self.id: int = cell_id
        self.parent_id: int | None = parent_id
        self.children_ids: list[int] = []
        self.birth_step: int = birth_step
        self.alive: bool = True
        self.state: CellState = state

    def __repr__(self) -> str:
        return (
            f"Cell(id={self.id}, parent={self.parent_id}, "
            f"alive={self.alive}, mutations={self.state.mutations})"
        )

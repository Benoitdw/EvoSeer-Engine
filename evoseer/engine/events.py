"""Event dataclasses produced by the Gillespie engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DivisionEvent:
    """A cell has divided, producing a child."""

    step: int
    parent_id: int
    child_id: int


@dataclass(frozen=True)
class DeathEvent:
    """A cell has died and been removed from the active pool."""

    step: int
    cell_id: int


@dataclass(frozen=True)
class DriverEvent:
    """A newly acquired mutation is flagged as a driver."""

    step: int
    cell_id: int
    mutation_id: int


@dataclass(frozen=True)
class SenescenceEvent:
    """A cell has entered permanent senescence (OIS fired)."""

    step: int
    cell_id: int

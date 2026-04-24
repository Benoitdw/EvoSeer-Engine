"""Lightweight context object passed to plugin callbacks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimContext:
    """
    Snapshot of the simulation state at a given Gillespie step.

    Passed read-only to every plugin method so plugins can condition their
    behaviour on time, population size, or step count without holding
    references to the engine.
    """

    t: float      # continuous time elapsed
    step: int     # current Gillespie step index
    N: int        # current number of living cells

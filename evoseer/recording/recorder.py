"""Recorder — three-tier event logging, periodic snapshots, final state dump."""

from __future__ import annotations

from dataclasses import dataclass, field

from evoseer.engine.events import DeathEvent, DriverEvent, DivisionEvent, SenescenceEvent


@dataclass
class Snapshot:
    """Population-level metrics captured every snapshot_interval steps."""

    step: int
    t: float
    n_alive: int
    n_dead_cumulative: int


@dataclass
class SimulationResult:
    """Complete output produced by the recorder at the end of a simulation."""

    # Per-event logs
    divisions: list[DivisionEvent] = field(default_factory=list)
    deaths: list[DeathEvent] = field(default_factory=list)
    drivers: list[DriverEvent] = field(default_factory=list)
    senescence: list[SenescenceEvent] = field(default_factory=list)

    # Periodic population snapshots
    snapshots: list[Snapshot] = field(default_factory=list)

    # Optional full mutational state of all living cells at termination
    final_mutations: dict[int, set[int]] | None = None

    # Human-readable stopping reason
    stop_reason: str = ""


class Recorder:
    """
    Accumulates simulation events, population snapshots, and final state.

    Three recording tiers (from the design doc §8):

    1. **Per-event** — every division, death, and driver acquisition is
       logged immediately with step-level resolution.

    2. **Periodic snapshots** — population-level metrics captured every
       ``snapshot_interval`` steps (configurable).

    3. **End-of-simulation** — full mutational state of all living cells,
       dumped when ``dump_final_state`` is True.
    """

    def __init__(
        self,
        snapshot_interval: int = 500,
        dump_final_state: bool = True,
    ) -> None:
        self._snapshot_interval = snapshot_interval
        self._dump_final_state = dump_final_state
        self._result = SimulationResult()
        self._n_dead: int = 0

    # ------------------------------------------------------------------
    # Per-event recording
    # ------------------------------------------------------------------

    def record_division(self, step: int, parent_id: int, child_id: int) -> None:
        """Log a division event."""
        self._result.divisions.append(DivisionEvent(step, parent_id, child_id))

    def record_death(self, step: int, cell_id: int) -> None:
        """Log a death event and increment the cumulative death counter."""
        self._result.deaths.append(DeathEvent(step, cell_id))
        self._n_dead += 1

    def record_driver(self, step: int, cell_id: int, mutation_id: int) -> None:
        """Log a driver acquisition event."""
        self._result.drivers.append(DriverEvent(step, cell_id, mutation_id))

    def record_senescence(self, step: int, cell_id: int) -> None:
        """Log a senescence event."""
        self._result.senescence.append(SenescenceEvent(step, cell_id))

    # ------------------------------------------------------------------
    # Periodic snapshots
    # ------------------------------------------------------------------

    def maybe_snapshot(self, step: int, t: float, n_alive: int) -> None:
        """
        Capture a population snapshot if the step falls on the interval.

        Call this at the end of every Gillespie step.
        """
        if step % self._snapshot_interval == 0:
            self._result.snapshots.append(
                Snapshot(step=step, t=t, n_alive=n_alive, n_dead_cumulative=self._n_dead)
            )

    # ------------------------------------------------------------------
    # End-of-simulation finalisation
    # ------------------------------------------------------------------

    def finalise(
        self,
        living_cells: dict[int, "Cell"],  # type: ignore[name-defined]  # forward ref
        stop_reason: str,
    ) -> SimulationResult:
        """
        Seal the result object and optionally dump full mutational state.

        Args:
            living_cells: Mapping of cell_id -> Cell for all surviving cells.
            stop_reason:  Human-readable description of why the simulation ended.

        Returns:
            The completed SimulationResult.
        """
        self._result.stop_reason = stop_reason
        if self._dump_final_state:
            self._result.final_mutations = {
                cid: set(cell.state.mutations)
                for cid, cell in living_cells.items()
            }
        return self._result
